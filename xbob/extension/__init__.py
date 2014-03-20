#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Mon 28 Jan 2013 16:40:27 CET

"""A custom build class for Pkg-config based extensions
"""

import sys
import os
import platform
from .pkgconfig import pkgconfig
from .boost import boost
from distutils.extension import Extension as DistutilsExtension

__version__ = __import__('pkg_resources').require('xbob.extension')[0].version

def uniq(seq):
  """Uniqu-fy preserving order"""

  seen = set()
  seen_add = seen.add
  return [ x for x in seq if x not in seen and not seen_add(x)]

def check_packages(packages):
  """Checks if the requirements for the given packages are satisfied.

  Raises a :py:class:`RuntimeError` in case requirements are not satisfied.
  This means either not finding a package if no version number is specified or
  verifying that the package version does not match the required version by the
  builder.

  Package requirements can be set like this::

    "pkg > VERSION"

  In this case, the package version should be greater than the given version
  number. Comparisons are done using :py:mod:`distutils.version.LooseVersion`.
  You can use other comparators such as ``<``, ``<=``, ``>=`` or ``==``. If no
  version number is given, then we only require that the package is installed.
  """

  from re import split

  used = set()
  retval = []

  for requirement in uniq(packages):

    splitreq = split(r'\s*(?P<cmp>[<>=]+)\s*', requirement)

    if len(splitreq) not in (1, 3):

      raise RuntimeError("cannot parse requirement `%s'", requirement)

    p = pkgconfig(splitreq[0])

    if len(splitreq) == 3: # package + version number

      if splitreq[1] == '>':
        assert p > splitreq[2], "%s version is not > `%s'" % (p.name, splitreq[2])
      elif splitreq[1] == '>=':
        assert p >= splitreq[2], "%s version is not >= `%s'" % (p.name, splitreq[2])
      elif splitreq[1] == '<':
        assert p < splitreq[2], "%s version is not < `%s'" % (p, splitreq[2])
      elif splitreq[1] == '<=':
        assert p <= splitreq[2], "%s version is not <= `%s'" % (p, splitreq[2])
      elif splitreq[1] == '==':
        assert p <= splitreq[2], "%s version is not == `%s'" % (p, splitreq[2])
      else:
        raise RuntimeError("cannot parse requirement `%s'", requirement)

    retval.append(p)

    if p.name in used:
      raise RuntimeError("package `%s' had already been requested - cannot (currently) handle recurring requirements")
    used.add(p.name)

  return retval

def generate_self_macros(extname, version):
  """Generates standard macros with library, module names and prefix"""

  s = extname.rsplit('.', 1)

  retval = [
      ('XBOB_EXT_MODULE_PREFIX', '"%s"' % s[0]),
      ('XBOB_EXT_MODULE_NAME', '"%s"' % s[1]),
      ]

  if sys.version_info[0] >= 3:
    retval.append(('XBOB_EXT_ENTRY_NAME', 'PyInit_%s' % s[1]))
  else:
    retval.append(('XBOB_EXT_ENTRY_NAME', 'init%s' % s[1]))

  if version: retval.append(('XBOB_EXT_MODULE_VERSION', '"%s"' % version))

  return retval


class Extension(DistutilsExtension):
  """Extension building with pkg-config packages.

  See the documentation for :py:class:`distutils.extension.Extension` for more
  details on input parameters.
  """

  def __init__(self, *args, **kwargs):
    """Initialize the extension with parameters.

    External package extensions (mostly comming from pkg-config), adds a single
    parameter to the standard arguments of the constructor:

    packages : [list]

      This should be a list of strings indicating the name of the bob
      (pkg-config) modules you would like to have linked to your extension
      **additionally** to ``bob-python``. Candidates are module names like
      "bob-machine" or "bob-math".

      For convenience, you can also specify "opencv" or other 'pkg-config'
      registered packages as a dependencies.
    """

    packages = []

    if 'packages' in kwargs and kwargs['packages']:
      if isinstance(kwargs['packages'], str):
        packages.append(kwargs['packages'])
      else:
        packages.extend(kwargs['packages'])

    if 'packages' in kwargs: del kwargs['packages']

    # Boost requires a special treatment
    boost_req = ''
    for i, pkg in enumerate(packages):
      if pkg.lower().startswith('boost'):
        boost_req = pkg.lower()
        del packages[i]

    # We still look for the keyword 'boost_modules'
    boost_modules = []
    if 'boost_modules' in kwargs and kwargs['boost_modules']:
      if isinstance(kwargs['boost_modules'], str):
        boost_modules.append(kwargs['boost_modules'])
      else:
        boost_modules.extend(kwargs['boost_modules'])

    if 'boost_modules' in kwargs: del kwargs['boost_modules']

    if boost_modules and not boost_req: boost_req = 'boost >= 1.0'

    # Was a version parameter given?
    version = None
    if 'version' in kwargs:
      version = kwargs['version']
      del kwargs['version']

    # Mixing
    parameters = {
        'define_macros': generate_self_macros(args[0], version),
        'extra_compile_args': ['-std=c++0x'], #synomym for c++11?
        'library_dirs': [],
        'libraries': [],
        }

    # Compilation options
    if platform.system() == 'Darwin':
      parameters['extra_compile_args'] += ['-Wno-#warnings']

    user_includes = kwargs.get('include_dirs', [])
    pkg_includes = []

    # Updates for boost
    if boost_req:

      # Adds include directory (enough for using just the template library)
      boost_pkg = boost(boost_req.replace('boost', '').strip())
      if boost_pkg.include_directory not in user_includes:
        parameters['extra_compile_args'].extend([
          '-isystem', boost_pkg.include_directory
          ])
        pkg_includes.append(boost_pkg.include_directory)

      # Adds specific boost libraries requested by the user
      if boost_modules:
        boost_libdir, boost_libraries = boost_pkg(boost_modules)
        parameters['library_dirs'].append(boost_libdir)
        parameters['libraries'].extend(boost_libraries)

    # Checks all other pkg-config requirements
    pkgs = check_packages(packages)

    for pkg in pkgs:

      # Adds parameters for each package, in order
      parameters['define_macros'] += pkg.package_macros()

      # Include directories are added with a special path
      for k in pkg.include_directories():
        if k in user_includes or k in pkg_includes: continue
        parameters['extra_compile_args'].extend(['-isystem', k])
        pkg_includes.append(k)

      parameters['define_macros'] += pkg.package_macros()
      parameters['library_dirs'] += pkg.library_directories()

      if pkg.name.find('bob-') == 0: # one of bob's packages

        # make-up the names of versioned Bob libraries we must link against

        if platform.system() == 'Darwin':
          libs = ['%s.%s' % (k, pkg.version) for k in pkg.libraries()]
        elif platform.system() == 'Linux':
          libs = [':lib%s.so.%s' % (k, pkg.version) for k in pkg.libraries()]
        else:
          raise RuntimeError("supports only MacOSX and Linux builds")

      else:

        libs = pkg.libraries()

      parameters['libraries'] += libs

    # Filter and make unique
    for key in parameters.keys():

      # Tune input parameters if they were set
      if key in kwargs: kwargs[key].extend(parameters[key])
      else: kwargs[key] = parameters[key]

      if key in ('extra_compile_args'): continue

      kwargs[key] = uniq(kwargs[key])

    # Uniq'fy parameters that are not on our parameter list
    kwargs['include_dirs'] = uniq(kwargs.get('include_dirs', []))

    # Make sure the language is correctly set to C++
    kwargs['language'] = 'c++'

    # On Linux, set the runtime path
    if platform.system() == 'Linux':
      kwargs.setdefault('runtime_library_dirs', [])
      kwargs['runtime_library_dirs'] += kwargs['library_dirs']
      kwargs['runtime_library_dirs'] = uniq(kwargs['runtime_library_dirs'])

    # Run the constructor for the base class
    DistutilsExtension.__init__(self, *args, **kwargs)

    # post-process the options since
    # there is an erroneous '-Wstrict-prototypes' in the environment options
    # see http://stackoverflow.com/questions/8106258/cc1plus-warning-command-line-option-wstrict-prototypes-is-valid-for-ada-c-o
    # note: this seems to work for python 2 only; for python 3, we still get the warnings...
    import distutils.sysconfig
    opt = distutils.sysconfig.get_config_var('OPT')
    os.environ['OPT'] = " ".join(flag for flag in opt.split() if flag != '-Wstrict-prototypes')

# gets sphinx autodoc done right - don't remove it
__all__ = [_ for _ in dir() if not _.startswith('_')]
