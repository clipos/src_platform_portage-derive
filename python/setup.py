#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2015-2018 ANSSI. All Rights Reserved.
#
# Setup script for portage-derive

import sys

from setuptools import setup

if sys.version_info.major > 2:
    raise Exception("Support for Python 2 only.")

setup(
    name='portage-derive',
    version='@VERSION@',
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
