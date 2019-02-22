#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2015-2018 ANSSI. All Rights Reserved.
#
# Setup script for portage-derive

import codecs
import os
import re
import sys

from setuptools import setup

if sys.version_info.major > 2:
    raise RuntimeError("Support for Python 2 only.")

# This current file:
here = os.path.abspath(os.path.dirname(__file__))

# Ugly functions that enable to have a single-source for the version string:
# See: https://packaging.python.org/guides/single-sourcing-package-version/
def read(*parts):
    with codecs.open(os.path.join(here, *parts), 'r') as fp:
        return fp.read()
def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

setup(
    name='portage-derive',
    version=find_version("portage_derive", "__init__.py"),
    description='Library/tool to automate Portage tree management',
    url='https://clip-os.org/',
    author='Mickaël Salaün',
    author_email='clipos@ssi.gouv.fr',
    packages=[
        'portage_derive',
    ],
    install_requires=[
        'portage>=2.3.13',
    ],
    extra_requires={
        'shell': ['ipython'],
    },
    entry_points={
        'console_scripts': [
            'portage-derive=portage_derive.__main__:main',
        ],
    },
)

# vim: set expandtab tabstop=4 softtabstop=4 shiftwidth=4:
