#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2015-2018 ANSSI. All Rights Reserved.
#
# Distutils script for clip-menu-xdg

from distutils.core import setup

setup(name = 'portage-derive',
      version = '@VERSION@',
      description = 'Library to manage packages metadata for CLIP',
      url = 'http://www.ssi.gouv.fr/',
      author = 'Mickaël Salaün',
      author_email = 'clipos@ssi.gouv.fr',
      packages = [
          'portage_derive'
          ]
      )

# vim: set expandtab tabstop=4 softtabstop=4 shiftwidth=4:
