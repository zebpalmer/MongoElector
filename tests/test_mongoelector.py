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
    """Test Mongoelector Functionality"""

    def setUp(self):
        """setup unittests"""
        pass

    def tearDown(self):
        """teardown unittests"""
        pass

    def test_000_init(self):
        """Smoke test"""
        MongoElector()


if __name__ == '__main__':
    import sys
    sys.exit(unittest.main())
