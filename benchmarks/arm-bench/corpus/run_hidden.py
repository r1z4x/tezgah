#!/usr/bin/env python3
"""Run a task's hidden test against the candidate tree.

argv[1] is the directory holding test_hidden_*.py. The candidate tree is the
cwd, inserted at sys.path[0] so the test imports the code under test rather
than anything near the test file itself.
"""
import os
import sys
import unittest

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, here)
suite = unittest.TestLoader().discover(sys.argv[1], pattern="test_hidden_*.py")
sys.exit(0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1)
