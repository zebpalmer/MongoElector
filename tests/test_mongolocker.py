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


import unittest

from mongoelector import MongoLocker
from pymongo import MongoClient


class TestMongoLocker(unittest.TestCase):

    def setUp(self):
        db = MongoClient().mongolocker
        db.locks.drop()       

    def tearDown(self):
        locks = MongoClient().mongolocker.locks       
        locks.drop()

    def test_001_init(self):
        db = MongoClient().mongolocker
        MongoLocker(key='testinit', dbconn=db)
        
    def test_002_cycle(self):
        db = MongoClient().mongolocker        
        ml = MongoLocker(key='testinit', dbconn=db)
        ml.aquire()
        self.assertTrue(ml.locked())
        ml.release()
        self.assertFalse(ml.locked())


if __name__ == '__main__':
    import sys
    sys.exit(unittest.main())
