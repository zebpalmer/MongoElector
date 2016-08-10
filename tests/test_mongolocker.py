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
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath('..'))
# noinspection PyPep8
from mongoelector import MongoLocker, LockExists
# noinspection PyPep8
from pymongo import MongoClient


class TestMongoLocker(unittest.TestCase):
    def setUp(self):
        MongoClient().ml_unittest.mongolocker.drop()

    def tearDown(self):
        MongoClient().ml_unittest.mongolocker.drop()

    def test_001_init(self):
        db = MongoClient()
        MongoLocker('testinit', db, dbname='ml_unittest')

    def test_002_cycle(self):
        db = MongoClient()
        ml = MongoLocker('testcycle', db, dbname='ml_unittest')
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

    def test_003_paranoid(self):
        db = MongoClient()
        ml = MongoLocker('testinit', db, dbname='ml_unittest', timeparanoid=True)
        ml._verifytime()

    def test_004_force_release(self):
        db = MongoClient()
        ml1 = MongoLocker('testrelease', db, dbname='ml_unittest')
        ml2 = MongoLocker('testrelease', db, dbname='ml_unittest')
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
        _acquireretry = MongoLocker._acquireretry
        start = datetime.utcnow()
        count = 0
        self.assertTrue(_acquireretry(True, start, 0, 0))  # initial entry
        with self.assertRaises(ValueError):
            _acquireretry(False, start, 30, 0)  # blocking false w/ timeout
        start = datetime.utcnow()
        self.assertTrue(_acquireretry(True, start, 10, 1))  # blocking true, count > 0
        self.assertTrue(_acquireretry(True, start, 10, 0))  # blocking true, count 0
        past = datetime.utcnow() - timedelta(minutes=1)
        self.assertFalse(_acquireretry(True, past, 50, 10))  # passed timeout
        self.assertFalse(_acquireretry(False, start, None, 1))  # non-blocking

if __name__ == '__main__':
    sys.exit(unittest.main())
