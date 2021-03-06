#!/usr/bin/python
# Copyright 2016 Andy Chu. All rights reserved.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
"""
libc_test.py: Tests for libc.py
"""

import unittest

import libc  # module under test


class LibcTest(unittest.TestCase):

  def testFnmatch(self):
    print(dir(libc))
    # pattern, string, result

    cases = [
        ('', '', 1),  # no pattern is valid
        ('a', 'a', 1),
        ('?', 'a', 1),
        ('\?', 'a', 0),
        ('\?', '?', 1),
        ('\\\\', '\\', 1),
        # What is another error?  Invalid escape is OK?
        ('\\', '\\', 0),  # no pattern is valid
    ]

    for pat, s, expected in cases:
      actual = libc.fnmatch(pat, s)
      self.assertEqual(expected, actual)

  def testGlob(self):
    print('GLOB')
    print(libc.glob('*.py'))

  def testRegex(self):
    #print(libc.regcomp(r'.*\.py'))
    print(libc.regex_parse(r'.*\.py'))
    print(libc.regex_parse(r'*'))
    print(libc.regex_parse('\\'))

    print(libc.regex_match(r'.*\.py', 'foo.py'))
    print(libc.regex_match(r'.*\.py', 'abcd'))
    # error
    print(libc.regex_match(r'*', 'abcd'))


if __name__ == '__main__':
  unittest.main()
