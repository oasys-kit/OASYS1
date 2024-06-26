#! /usr/bin/env python3

from importlib.machinery import SourceFileLoader
import os
import subprocess
import platform

from setuptools import setup

NAME = 'OASYS1'

VERSION = '1.2.146'

ISRELEASED = True

DESCRIPTION = 'OrAnge SYnchrotron Suite'
README_FILE = os.path.join(os.path.dirname(__file__), 'README.md')
LONG_DESCRIPTION = open(README_FILE).read()
AUTHOR = 'Luca Rebuffi, Manuel Sanchez del Rio and Bioinformatics Laboratory, FRI UL'
AUTHOR_EMAIL = 'lrebuffi@anl.gov'
URL = 'https://github.com/oasys-kit/OASYS1'
DOWNLOAD_URL = 'https://github.com/oasys-kit/OASYS1'
MAINTAINER = 'Luca Rebuffi, Argonne National Lab, USA'
MAINTAINER_EMAIL = 'lrebuffi@anl.gov'
LICENSE = 'GPLv3'

KEYWORDS = (
    'ray tracing',
    'simulation',
)

CLASSIFIERS = (
    'Development Status :: 5 - Production/Stable',
    'Environment :: X11 Applications :: Qt',
    'Environment :: Console',
    'Environment :: Plugins',
    'Programming Language :: Python :: 3',
    'License :: OSI Approved :: '
    'GNU General Public License v3 or later (GPLv3+)',
    'Operating System :: POSIX',
    'Operating System :: Microsoft :: Windows',
    'Topic :: Scientific/Engineering :: Visualization',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Intended Audience :: Education',
    'Intended Audience :: Science/Research',
    'Intended Audience :: Developers',
)

INSTALL_REQUIRES = (
    'setuptools',
    'requests',
    'numpy<1.23,>=1.21',
    'fabio==0.11.0',
    'PyQt5==5.15.2',
    'scipy<=1.9.1,>=1.7.3',
    'matplotlib<=3.5.3,>=3.3.2',
    'oasys-canvas-core>=1.0.7',
    'oasys-widget-core>=1.0.3',
    'silx==0.15.0',
    'hdf5plugin',
    'srxraylib>=1.0.28',
    'syned>=1.0.28',
    'wofry>=1.0.31',
)


try:
    system, node, release, version, machine, processor = platform.uname()
    if "Debian 3" in version:
        l1 = list(INSTALL_REQUIRES)
        for i,element in enumerate(l1):
            if "PyQt5" in element:
                l1[i] = "PyQt5==5.11.3"
        INSTALL_REQUIRES = tuple(l1)
except:
    pass


SETUP_REQUIRES = (
    'setuptools',
)

# Return the git revision as a string
def git_version():
    """Return the git revision as a string.

    Copied from numpy setup.py
    """
    def _minimal_ext_cmd(cmd):
        # construct minimal environment
        env = {}
        for k in ['SYSTEMROOT', 'PATH']:
            ver = os.environ.get(k)
            if ver is not None:
                env[k] = ver
        # LANGUAGE is used on win32
        env['LANGUAGE'] = 'C'
        env['LANG'] = 'C'
        env['LC_ALL'] = 'C'
        out = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env).communicate()[0]
        return out

    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', 'HEAD'])
        git_revision = out.strip().decode('ascii')
    except OSError:
        git_revision = "Unknown"

    return git_revision


def write_version_py(filename='oasys/version.py'):
    # Copied from numpy setup.py
    cnt = """
# THIS FILE IS GENERATED FROM OASYS SETUP.PY
short_version = '%(version)s'
version = '%(version)s'
full_version = '%(full_version)s'
git_revision = '%(git_revision)s'
release = %(isrelease)s

if not release:
    version = full_version
    short_version += ".dev"
"""
    full_version = VERSION
    if os.path.exists('.git'):
        git_revision = git_version()
    elif os.path.exists('oasys/version.py'):
        # must be a source distribution, use existing version file
        version = SourceFileLoader('oasys.version', 'oasys/version.py').load_module()
        git_revision = version.git_revision
    else:
        git_revision = "Unknown"

    if not ISRELEASED:
        full_version += '.dev0+' + git_revision[:7]

    with open(filename, 'w') as file:
        file.write(cnt % {'version': VERSION,
                          'full_version': full_version,
                          'git_revision': git_revision,
                          'isrelease': str(ISRELEASED)})

PACKAGES = (
    "oasys",
    "oasys.canvas",
    "oasys.canvas.styles",
    "oasys.menus",
    "oasys.widgets",
    "oasys.widgets.tools",
    "oasys.widgets.loop_management",
)

PACKAGE_DATA = {
    "oasys.application": ["data/*.txt"],
    "oasys.canvas": ["icons/*.png", "icons/*.svg"],
    "oasys.canvas.styles": ["*.qss", "orange/*.svg"],
    "oasys.widgets.tools": ["icons/*.png", "icons/*.svg", "misc/*.png"],
    "oasys.widgets.loop_management": ["icons/*.png", "icons/*.svg"],
    "oasys.widgets.scanning": ["icons/*.png", "icons/*.svg"],
}

ENTRY_POINTS = {
    'oasys.widgets' : (
        "Oasys Tools = oasys.widgets.tools",
        "Oasys Basic Loops = oasys.widgets.loop_management",
        "Oasys Scanning Loops = oasys.widgets.scanning",
    )
}

def setup_package():
    write_version_py()
    setup(
        name=NAME,
        version=VERSION,
        description=DESCRIPTION,
        long_description=LONG_DESCRIPTION,
        author=AUTHOR,
        author_email=AUTHOR_EMAIL,
        maintainer=MAINTAINER,
        maintainer_email=MAINTAINER_EMAIL,
        url=URL,
        download_url=DOWNLOAD_URL,
        license=LICENSE,
        keywords=KEYWORDS,
        classifiers=CLASSIFIERS,
        packages=PACKAGES,
        package_data=PACKAGE_DATA,
        entry_points=ENTRY_POINTS,
        # extra setuptools args
        zip_safe=False,  # the package can run out of an .egg file
        include_package_data=True,
        install_requires=INSTALL_REQUIRES,
        setup_requires=SETUP_REQUIRES,
    )

if __name__ == '__main__':
    setup_package()
