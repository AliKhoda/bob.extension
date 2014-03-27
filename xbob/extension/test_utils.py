#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Thu 20 Mar 2014 12:43:48 CET

"""Tests for file search utilities
"""

import os
import sys
import nose.tools
from .utils import uniq, egrep, find_file, find_header, find_library

def test_uniq():

  a = [1, 2, 3, 7, 3, 2]

  nose.tools.eq_(uniq(a), [1, 2, 3, 7])

def test_find_file():

  f = find_file('array.h', subpaths=[os.path.join('include', 'blitz')])

  assert f

  nose.tools.eq_(len(f), 1)

  nose.tools.eq_(os.path.basename(f[0]), 'array.h')

def test_find_header():

  f1 = find_file('array.h', subpaths=[os.path.join('include', 'blitz')])

  assert f1

  nose.tools.eq_(len(f1), 1)

  nose.tools.eq_(os.path.basename(f1[0]), 'array.h')

  f2 = find_header(os.path.join('blitz', 'array.h'))

  nose.tools.eq_(len(f2), 1)

  nose.tools.eq_(os.path.basename(f2[0]), 'array.h')

  assert f2

  nose.tools.eq_(f1, f2)

def test_find_library():

  f = find_library('blitz')

  assert f

  assert len(f) >= 1

  for k in f:
    assert k.find('blitz') >= 0

def test_egrep():

  f = find_header('version.hpp', subpaths=['boost', 'boost?*'])

  assert f

  nose.tools.eq_(len(f), 1)

  matches = egrep(f[0], r"^#\s*define\s+BOOST_VERSION\s+(\d+)\s*$")

  nose.tools.eq_(len(matches), 1)

def test_find_versioned_library():

  f = find_header('version.hpp', subpaths=['boost', 'boost?*'])

  assert f

  nose.tools.eq_(len(f), 1)

  matches = egrep(f[0], r"^#\s*define\s+BOOST_VERSION\s+(\d+)\s*$")

  nose.tools.eq_(len(matches), 1)

  version_int = int(matches[0].group(1))
  version_tuple = (
      version_int // 100000,
      (version_int // 100) % 1000,
      version_int % 100,
      )
  version = '.'.join([str(k) for k in version_tuple])

  lib = find_library('boost_system', version=version)
  lib += find_library('boost_system-mt', version=version)

  assert len(lib) >= 1

  for k in lib:
    assert k.find('boost_system') >= 0
