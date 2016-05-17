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
        db = MongoClient().mongolocker.locks
        db.locks.drop()

    def tearDown(self):
        locks = MongoClient().mongolocker.locks
        locks.drop()

    def test_001_init(self):
        db = MongoClient().mongolocker.locks
        MongoLocker(key='testinit', dbconn=db)

    def test_002_cycle(self):
        db = MongoClient().mongolocker.locks
        ml = MongoLocker(key='testinit', dbconn=db)
        ml.aquire()
        self.assertTrue(ml.locked())
        ml.release()
        self.assertFalse(ml.locked())


if __name__ == '__main__':
    sys.exit(unittest.main())
