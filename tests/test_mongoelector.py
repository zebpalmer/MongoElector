#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_mongoelector
----------------------------------

Tests for `mongoelector` module.
"""

import unittest

from mongoelector import MongoElector


class TestMongoelector(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_000_init(self):
        MongoElector()


if __name__ == '__main__':
    import sys
    sys.exit(unittest.main())
