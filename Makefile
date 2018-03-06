# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2015-2018 ANSSI. All Rights Reserved.
# For other distro than Gentoo

PREFIX ?= /usr
PORTAGE ?= $(shell readlink -f portage)
SHARE_DIR = $(DESTDIR)$(PREFIX)/share/clip-pkgdb
BIN_DIR = $(DESTDIR)$(PREFIX)/bin

.PHONY: all install

all:

install:
	install -d $(SHARE_DIR)/bin
	umask 0022; rsync --recursive --links --chmod=u=rwX,go=rX --exclude '*.pyc' --exclude '*.pyo' bin python $(PORTAGE) $(SHARE_DIR)
	install -d $(BIN_DIR)
	ln -s ../share/clip-pkgdb/bin/clip-pkgdb-wrapper $(BIN_DIR)/clip-pkgdb
