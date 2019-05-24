#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2015-2018 ANSSI. All Rights Reserved.
#
# Tool to automate Portage tree management.
#
# Author: Mickaël Salaün <clipos@ssi.gouv.fr>

import argparse
import logging

from . import MultiDb, equalize

def _print_atom(mdb, atom):
    slot, keywords = mdb.aux_get_first(atom, ["SLOT", "KEYWORDS"])
    print("{} slot:{} keywords:{}".format(atom, slot, keywords))

def main_list(args):
    mdb = MultiDb(args.portdir, args.profile)
    for pkg in args.packages:
        atoms = mdb.match_visibles(pkg)
        if atoms == "":
            print("Failed to find a package named \"{}\"".format(pkg))
            return 1
        if isinstance(atoms, set):
            for atom in atoms:
                _print_atom(mdb, atom)
        else:
            _print_atom(mdb, atoms)

def main_shell(args):
    from IPython.terminal.embed import InteractiveShellEmbed
    import portage
    mdb = MultiDb(args.portdir, args.profile)
    banner = "Use the \"mdb\" object to explore the Portage databases."
    ipshell = InteractiveShellEmbed(banner1=banner)
    ipshell()

def main_equalize(args):
    mdb = MultiDb(args.portdir, args.profile)
    equalize(mdb, atoms=args.packages, dry_run=args.dry_run)

def main():
    parser = argparse.ArgumentParser(description="Tool to automate Portage tree management.")

    parser.add_argument("-d", "--portdir", help="Portage tree directory", required=True)
    parser.add_argument("-n", "--dry-run", help="do not perform any action on the file system", action="store_true")
    parser.add_argument("-p", "--profile", help="Portage profile(s)", action="append", required=True)
    parser.add_argument("-q", "--quiet", help="do not output anything except errors", action="store_true")
    parser.add_argument("-v", "--verbose", help="print debug informations", action="store_true")
    subparser = parser.add_subparsers()

    parser_list = subparser.add_parser("list", help="list visible ebuilds for a given package/atom (must give at least one package/atom)")
    parser_list.add_argument("packages", help="packages or atoms", nargs="+")
    parser_list.set_defaults(func=main_list)

    parser_shell = subparser.add_parser("shell", help="launch an IPython shell to hack with the Portage tree database")
    parser_shell.set_defaults(func=main_shell)

    parser_equalize = subparser.add_parser("equalize", help="equalize a Portage tree (make it Git-friendly to ease merges with stable ebuild names and their symlinks); operate on the whole tree if no package/atom is given; otherwise operate on given packages/atoms only")
    parser_equalize.add_argument("packages", help="packages or atoms", nargs="*", default=[])
    parser_equalize.set_defaults(func=main_equalize)

    args = parser.parse_args()
    if not args.quiet:
        if args.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
    args.func(args)

if __name__ == '__main__':
    main()
