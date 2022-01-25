#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_mongoelector
----------------------------------

Tests for `mongoelector` module.
"""

import os
import sys
import unittest
import time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath('..'))
# noinspection PyPep8
from mongoelector import MongoLocker, LockExists
# noinspection PyPep8
from mongomock import MongoClient


class TestMongoLocker(unittest.TestCase):
    """Test MongoLocker Functionality"""

    def test_001_init(self):
        """Smoke test"""
        db = MongoClient().db
        MongoLocker('testinit', db)


    def test_002_cycle(self):
        """run some lock cycles"""
        db = MongoClient().db

        ml = MongoLocker('testcycle', db)
        if ml.locked():  # cleanup any leftovers
            ml.release(force=False)
        ml.acquire()
        self.assertTrue(ml.locked())
        self.assertTrue(ml.owned())
        ml.release()
        self.assertFalse(ml.owned())
        self.assertFalse(ml.locked())
        ml.acquire()
        ml.release(force=False)
        self.assertFalse(ml.locked())

    # def test_003_paranoid(self):
    #     """test time paranoia"""
    #     db = getattr(MongoClient(), "ml_unittest")
    #     ml = MongoLocker('testinit', db, timeparanoid=True)
    #     ml._verifytime()

    def test_004_force_release(self):
        """Force releases"""
        db = MongoClient().db
        ml1 = MongoLocker('testrelease', db)
        ml2 = MongoLocker('testrelease', db)
        ml1.acquire()
        with self.assertRaises(LockExists):
            ml2.acquire(blocking=False)
        ml2.release()
        self.assertTrue(ml1.locked())
        self.assertTrue(ml1.owned())
        ml2.release(force=True)
        self.assertFalse(ml1.locked())
        self.assertFalse(ml1.owned())

    def test_005_acquire_retry(self):
        """Test method that determines if an acquire retry is appropriate"""
        _acquireretry = MongoLocker._acquireretry
        start = datetime.utcnow()
        self.assertTrue(_acquireretry(True, start, 0, 0))  # initial entry
        with self.assertRaises(ValueError):
            _acquireretry(False, start, 30, 0)  # blocking false w/ timeout
        start = datetime.utcnow()
        self.assertTrue(_acquireretry(True, start, 10, 1))  # blocking true, count > 0
        self.assertTrue(_acquireretry(True, start, 10, 0))  # blocking true, count 0
        past = datetime.utcnow() - timedelta(minutes=1)
        self.assertFalse(_acquireretry(True, past, 50, 10))  # passed timeout
        self.assertFalse(_acquireretry(False, start, None, 1))  # non-blocking

    def test_006_acquire_force(self):
        """Test stealing the lock"""
        db = getattr(MongoClient(), "testcycle")
        a = MongoLocker('testcycle', db)
        b = MongoLocker('testcycle', db)
        a.acquire()
        self.assertTrue(a.owned())
        self.assertTrue(b.acquire(force=True))
        self.assertTrue(b.owned())
        self.assertFalse(a.owned())
        a.release()
        b.release()
        self.assertFalse(a.locked())
        self.assertFalse(b.locked())

    def test_007_touch(self):
        """ensure touch updates the expiration timestamp"""
        db = getattr(MongoClient(), "ml_unittest")
        ml = MongoLocker('testtouch', db)
        ml.acquire()
        start = ml.ts_expire
        time.sleep(1)
        self.assertTrue(ml.touch())
        end = ml.ts_expire
        self.assertTrue(end > start)

    def test_008_status(self):
        """Test lock status property"""
        db = getattr(MongoClient(), "ml_unittest")
        ml = MongoLocker('teststatus', db)
        a = ml.status
        self.assertIsInstance(a['pid'], int)
        # Test Unlocked
        self.assertEqual(a['lock_created'], None)
        self.assertEqual(a['lock_expires'], None)
        self.assertEqual(a['lock_owned'], False)
        # Test Locked
        ml.acquire()
        b = ml.status
        self.assertEqual(b['lock_owned'], True)
        self.assertIsInstance(b['lock_expires'], datetime)
        self.assertIsInstance(b['lock_created'], datetime)

if __name__ == '__main__':
    sys.exit(unittest.main())
