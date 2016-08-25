#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_mongoelector
----------------------------------

Tests for `mongoelector` module.
"""

import unittest
from time import sleep
from pymongo import MongoClient
from mongoelector import MongoElector
from random import randint


class TestMongoelector(unittest.TestCase):
    """Test Mongoelector Functionality"""

    def setUp(self):
        """setup unittests"""
        MongoClient().ml_unittest.electorlocks.drop()


    def tearDown(self):
        """teardown unittests"""
        MongoClient().ml_unittest.electorlocks.drop()


    def test_000_init(self):
        """Smoke test"""
        MongoElector('test_001_init', MongoClient())

    def test_001_run(self):
        m1 = MongoElector('test_001_run_' + str(randint(0,10000)), MongoClient(),
                          dbname='ml_unittest',ttl=15)
        m1.start()
        c = 0
        while c < 30 and m1.ismaster is False:
            c += 1
            sleep(1)
        self.assertTrue(m1.ismaster)
        self.assertTrue(m1.running)
        m1.poll()
        self.assertIsInstance(m1.cluster_detail, dict)
        m1.stop()
        m1.poll()
        c = 0
        while c < 30 and m1.ismaster is True:
            c += 1
            sleep(1)
        self.assertFalse(m1.ismaster)




if __name__ == '__main__':
    import sys
    sys.exit(unittest.main())
