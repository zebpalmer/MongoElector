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


from mongoelector import MongoLocker
from pymongo import MongoClient

import unittest



class TestMongoLocker(unittest.TestCase):

    def setUp(self):
        db = MongoClient().mongoelector.mongolocker
        db.locks.drop()

    def tearDown(self):
        locks = MongoClient().mongoelector.mongolocker
        locks.drop()

    def test_001_init(self):
        db = MongoClient()
        MongoLocker(key='testinit', dbconn=db)

    def test_002_cycle(self):
        db = MongoClient()
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

    def test_003_paranoid(self):
        db = MongoClient()
        ml = MongoLocker('testinit', db, timeparanoid=True)
        ml._verifytime()



if __name__ == '__main__':
    sys.exit(unittest.main())
