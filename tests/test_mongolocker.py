#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_mongoelector
----------------------------------

Tests for `mongoelector` module.
"""

import os
import sys
sys.path.insert(0, os.path.abspath('..'))


from mongoelector import MongoLocker, LockExists
from pymongo import MongoClient

import unittest



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


if __name__ == '__main__':
    sys.exit(unittest.main())
