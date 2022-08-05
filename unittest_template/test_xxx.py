#! /usr/bin/python

import pprint
import unittest

from unittest_main.test_common import GmTestCaseCommon

class GmTestCaseTemplate(GmTestCaseCommon):
    #@unittest.skip
    def test_template(self):
        assert(1)
