#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2015-2018 ANSSI. All Rights Reserved.
#
# Tool to link metadata to packages in a standalone text database optimized for
# version control systems.
#
# Copyright 2015 ANSSI
# Author: Mickaël Salaün <clipos@ssi.gouv.fr>
#
# All rights reserved

from datetime import datetime
from dateutil import parser as dateparser
from dateutil import tz
from lxml import etree
import ConfigParser
import distutils.version as version
import glob
import os
import portage
import re
import shutil
import subprocess
import sys
import urllib2

CLIP_BUILD_PATH = "/etc/clip-build.conf"
CLIP_INT_PKGDB_PATH = "pkgdb/all.conf"
CLIP_INT_SPECS = "specs"
DISTFILES_BASENAME = "distfiles"
PORTAGE_BASENAME = "portage"
PORTAGE_METADATA_CPE_XPATH = "/pkgmetadata/upstream/remote-id[@type=\"cpe\"]"
PORTAGE_PROFILES = ("hardened/linux/x86", "hardened/x86/2.6", "default/linux/x86", "default-linux/x86")

# ISO format with forced UTC
DATE_ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def get_clip_base(do_raise):
    base_re = re.compile(r"^CLIP_BASE=\"?([^\"]+)\"$", re.MULTILINE)
    try:
        with open(CLIP_BUILD_PATH) as clip_build:
            base_path = base_re.search(clip_build.read())
            if base_path:
                return base_path.group(1)
            if do_raise:
                raise Exception("No CLIP_BASE variable in {}".format(CLIP_BUILD_PATH))
    except:
        pass
    return None

def get_atom_fields(path):
    portage_re = re.compile("^.*(portage[^/]*)/([^/]+)/([^/]+)/[^/]+-([0-9].*)\.ebuild$", re.MULTILINE)
    portage_split = portage_re.search(path)
    if portage_split:
        return portage_split.groups()
    return None

class Package(object):
    # CPEs: Common Platform Enumeration
    def __init__(self, (portage, category, name, version_ebuild), section=None, extra=[], last_checked=None, cpes=set(),deb_suffixes=dict(),slot=None,broken=None,masked=None, priorities={}):
        self.portage = portage
        self.category = category
        self.name = name
        self.version_ebuild = version.LooseVersion(version_ebuild)
        self.last_checked = last_checked
        # TODO: add fields
        #self.version_changelog = version.LooseVersion(version_changelog)
        #self.arch_x86 = none | stable | unstable
        #self.arch_arm = none | stable | unstable
        #self.arch_amd64 = none | stable | unstable
        self._section = section
        # Inherit old (custom) fields, if any (e.g. "last-check" or "comment")
        self._extra = extra
        self.cpes = set()
        self.add_cpes(cpes)
        self.deb_suffixes=dict()
        self.priority={}
        self.add_deb_suffixes(deb_suffixes)
        self.add_priority(priorities)
        self.slot=slot
        self.broken=broken
        self.masked=masked

    def add_cpes(self, cpes):
        self.cpes.update(cpes)

    def add_deb_suffixes(self,suffixes):
        for a in suffixes.keys():
            if self.deb_suffixes.has_key(a):
                self.deb_suffixes[a]+=" {}".format(suffixes[a])
            else:
                self.deb_suffixes[a]=suffixes[a]

    def add_priority(self,priorities):
        for a in priorities.keys():
            if self.priority.has_key(a):
                self.priority[a]+=" {}".format(priorities[a])
            else:
                self.priority[a]=priorities[a]

    def __str__(self):
        return self.af

    def __repr__(self):
        return "Package({})".format(self.af)

    def __cmp__(self, other):
        atom_cmp = cmp(self._reverse_atom, other._reverse_atom)
        # Different package: increase alphabetical order
        if atom_cmp != 0:
            return atom_cmp
        # Same package but different version: decrease order to keep the most up to date at first
        # It's more common to remove an old package version than the more up-to-date (i.e. we don't downgrade packages but can keep and old version for compatibility).
        return cmp(self.version_ebuild, other.version_ebuild) * -1

    @property
    def _reverse_atom(self):
        return "{}/{}".format(self.name, self.category)

    @property
    def pf(self):
        return "{}-{}".format(self.name, self.version_ebuild.vstring)

    @property
    def atom(self):
        return "{}/{}".format(self.category, self.name)

    @property
    def af(self):
        return "{}-{}".format(self.atom, self.version_ebuild.vstring)

    @property
    def path(self):
        return "{}/{}/{}-{}.ebuild".format(self.portage, self.atom, self.name, self.version_ebuild.vstring)

    @property
    def _fields(self):
        fields = self._extra
        fields += [("portage-tree", self.portage)]
        fields += [("category", self.category)]
        fields += [("name", self.name)]
        fields += [("version-clip", self.version_ebuild.vstring)]
        if self.last_checked is not None:
            fields += [("last-checked", self.last_checked.strftime(DATE_ISO_FORMAT))]
        # TODO: Add a version-upstream/version_changelog infered from the ChangeLog for portage-overlay (i.e. our ebuild versions can fork from the Gentoo ones).
        if len(self.cpes) > 0:
            fields += [("cpes", " ".join(sorted(self.cpes)))]
        if (self.deb_suffixes):
            for k in self.deb_suffixes.keys():
                fields += [("{}_deb_suffix".format(k),self.deb_suffixes[k])]
        if (self.priority):
            for k in self.priority.keys():
                fields += [("{}_priority".format(k),self.priority[k])]
        # FIXME passer deb_suffix en list +sorted
        if self.slot:
            fields += [('slot',self.slot)]
        if self.broken:
            fields += [("broken",self.broken)]
        if self.masked:
            fields += [("masked",self.masked)]
        fields.sort()
        return fields

    # ------------------------------------------------------------
    # for a given clip-pkgdb object
    # return the list of spec files that define its compilation
    # for CLIP
    def getSpecFilesForPkg(self):
        spec_files_list=[]
        spec_path = get_clip_base(False)+"/"
        for spec in glob.glob(os.path.join(spec_path,"specs","clip*","*.xml")):
            res = subprocess.check_output(["cpp",spec])
            description=self.category+"/"+self.name
            if description in res:
                spec_files_list.append(getSpecFileShortName(spec))
        return spec_files_list


def get_cpes(path):
    ret = []
    try:
        with open(path) as f:
            tree = etree.parse(f)
            match = tree.xpath(PORTAGE_METADATA_CPE_XPATH)
            for child in match:
                cpe = child.text.strip()
                if len(cpe) > 0:
                    ret += [cpe]
    except IOError, e:
        pass
    return ret

def get_suffix(dico,pkg):
    ret = {}
    reg=re.compile("DEB_NAME_SUFFIX=([^,<]+)");
    #First deal with "STATIC" DEB SUFFIXES
    for i in dico.keys():
        llnodes=map(lambda x:x.xpath("//pkg[contains(pkgnames,'{}') and contains(env,'DEB_NAME_SUFFIX')]".format(pkg.atom)),dico[i])
        nodes=[n for ln in llnodes for n in ln]
        if nodes:
            for n in nodes:
                envstring=n.find('env').text
                suff=reg.search(envstring).group(1)
                tmp=n.find('pkgkey').text;
                pacnam=n.find('pkgnames').text
                match=re.search('={}-([^*]+)'.format(re.sub('\+',r'\+',pkg.atom)),pacnam)
                if match:
                    if not pkg.version_ebuild.vstring.startswith(match.group(1)):
                        continue
                match=re.search(r'{}:(\S+)'.format(re.sub('\+',r'\+',pkg.atom)),pacnam)
                if match:
                    if not pkg.slot == match.group(1):
                        continue
                if ret.has_key(i) \
                    and not re.search(r"\b{}\b".format(suff),ret[i]):
                    ret[i]+=" {}".format(suff)
                else:
                    ret[i]=suff
    #Next deal with SLOTS as suffixes
    for i in dico.keys():
        llnodes=map(lambda x:x.xpath("//pkg[contains(pkgnames,'{}') and contains(env,'DEB_SLOT_NAME_SUFFIX=yes')]".format(pkg.atom)),dico[i])
        nodes=[n for ln in llnodes for n in ln]
        if nodes:
            for n in nodes:
                tmp=n.find('pkgkey').text;
                pacnam=n.find('pkgnames').text
                match=re.findall(r'\b{}:(\S+)'.format(re.sub('\+',r'\+',pkg.atom)),pacnam)
                for suff in match:
                    if not pkg.slot == suff:
                        continue
                    if ret.has_key(i) \
                        and not re.search(r"\b{}\b".format(suff),ret[i]):
                            ret[i]+=" {}".format(suff)
                    else:
                        ret[i]=suff
    #Finally deal with node without env variable altering the name
    for i in dico.keys():
        llnodes=map(lambda x:x.xpath("//pkg[contains(pkgnames,'{}') and not(contains(env,'DEB_'))]".format(pkg.atom)),dico[i])
        nodes=[n for ln in llnodes for n in ln]
        if nodes:
            for n in nodes:
                pacnam=n.find('pkgnames').text
                match=re.search('={}-([^*]+)'.format(re.sub('\+',r'\+',pkg.atom)),pacnam)
                if match:
                    if not pkg.version_ebuild.vstring.startswith(match.group(1)):
                        continue
                match=re.search(r'{}:(\S+)'.format(re.sub('\+',r'\+',pkg.atom)),pacnam)
                if match:
                    if not pkg.slot == match.group(1):
                        continue
                if ret.has_key(i) \
                    and not re.search(r"\b_\b",ret[i]):
                    ret[i]+=" {}".format('_')

    return ret;

def get_package_deb_priority(dico,pkg):
    ret = {}
    reg=re.compile("DEB_PRIORITY=(\w*)");
    for i in dico.keys():
        ret[i]=""
        llnodes=map(lambda x:x.xpath("//config/pkg/pkgnames[contains(.,'{}')]/../env".format(pkg.atom)),dico[i])
        nodes=[n for ln in llnodes for n in ln]
        if nodes:
            for n in nodes:
                envstring=n.text
                search_res = reg.search(envstring)
                if ( search_res != None) :
                    if (search_res.group(1) not in ret[i]):
                        ret[i]+=search_res.group(1)+" "

        llnodes=map(lambda x:x.xpath("//config/pkg/pkgnames[contains(.,'{}')]/../../env".format(pkg.atom)),dico[i])
        nodes=[n for ln in llnodes for n in ln]
        if nodes:
            for n in nodes:
                envstring=n.text
                search_res = reg.search(envstring)
                if ( search_res != None) :
                    if (search_res.group(1) not in ret[i]):
                        ret[i]+=search_res.group(1)+" "

        ret[i]=ret[i].strip()

        if (ret[i] == ""):
            ret.pop(i)

    return ret

def all_ebuild(base):
    for portage in ["portage", "portage-overlay", "portage-overlay-clip", "portage-overlay-dev"]:
        portage_path = "{}/{}".format(base, portage)
        for root, dirs, files in os.walk(portage_path):
            for name in files:
                fields = get_atom_fields(os.path.join(root, name))
                if fields is not None:
                    yield Package(fields)

# Config file example:
#
# [foo.0]
# category = bar
# cpes = cpe:/a:foo.org:foo cpe:/a:foo.org:libfoo
# name = foo
# portage-tree = portage-overlay
# version-clip = 1.4.0
#
# [foo.1]
# category = bar
# name = foo
# portage-tree = portage-overlay
# version-clip = 1.3.0-r2

class PackageDb(object):
    def __init__(self, config_name, workdir=None):
        self._db = []
        self.file_path = config_name
        if workdir is None:
            self.workdir = get_clip_base(True)
        else:
            self.workdir = workdir

    def __repr__(self):
        return "PackageDb({})".format(self._db)

    def __iter__(self):
        return self._db.__iter__()

    def load(self):
        config = ConfigParser.RawConfigParser()

        # Load existing config, if any
        try:
            with open(self.file_path) as config_fd:
                config.readfp(config_fd)
        except IOError as e:
            if e.errno != os.errno.ENOENT:
                raise e

        for section in config.sections():
            pkg_portage = None
            pkg_category = None
            pkg_name = None
            pkg_version = None
            pkg_last_checked = None
            pkg_cpes = []
            pkg_deb_suffixes = {}
            pkg_priority = {}
            pkg_slot = None
            pkg_masked = None
            pkg_broken = None
            extra = []
            for name, value in config.items(section):
                if name == "portage-tree":
                    pkg_portage = value
                elif name == "category":
                    pkg_category = value
                elif name == "name":
                    pkg_name = value
                elif name == "version-clip":
                    pkg_version = value
                elif name == "last-checked":
                    # Optional field
                    # Fix timezone (Python 2 bug)
                    pkg_last_checked = datetime.strptime(value, DATE_ISO_FORMAT).replace(tzinfo=tz.tzutc())
                elif name == "cpes":
                    pkg_cpes = value.split()
                elif name.endswith("deb_suffix"):
                    pkg_deb_suffixes[name[0:len(name)-11]]=value
                elif name.endswith("priority"):
                    pkg_priority[name[0:len(name)-9]]=value
                elif name == "slot":
                    pkg_slot = value
                elif name == "masked":
                    pkg_masked = value
                elif name == "broken":
                    pkg_broken = value
                else:
                    extra += [(name, value)]
            if pkg_portage is None or pkg_category is None or pkg_name is None or pkg_version is None:
                raise Exception("Failed to get all mandatory fields for {}".format(section))
            self._db+=[ Package((pkg_portage,pkg_category,pkg_name,pkg_version),\
            section,\
            extra, \
            pkg_last_checked,\
            pkg_cpes,\
            pkg_deb_suffixes,\
            pkg_slot,\
            pkg_broken,\
            pkg_masked,\
            pkg_priority)]

        self._refresh()

    def _has_section(self, section):
        if self._get_section(section) is None:
            return False
        return True

    def _get_section(self, section):
        if section is None:
            return None
        for pkg in self._db:
            if pkg._section == section:
                return pkg
        return None

    def _refresh(self):
        # Sort sections and fields (future-proof) for deterministic output
        self._db.sort()
        for pkg in self._db:
            if pkg._section is not None:
                continue
            i = 0
            def new_section():
                return "{}.{}".format(pkg.name, i)
            section = new_section()
            while self._has_section(section):
                i += 1
                section = new_section()
            pkg._section = section

    def save(self):
        config_new = ConfigParser.RawConfigParser()

        for pkg in self._db:
            config_new.add_section(pkg._section)
            for name, value in pkg._fields:
                config_new.set(pkg._section, name, value)

        with open(self.file_path, "w") as config_fd:
            config_new.write(config_fd)

    def _update_ebuild(self):
        self._db = [x for x in all_ebuild(self.workdir)]

    def _update_vcs(self):
        date_re = re.compile(r"^Last Changed Date: ([0-9 :+-]{25}) .*", re.MULTILINE)
        path_re = re.compile(r"^Path: (.*)$", re.MULTILINE)
        paths = []
        for pkg in self._db:
            paths += [pkg.path]
        proc = subprocess.Popen(["svn", "info", "--"] \
        + paths, cwd=self.workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pkg_iter = self._db.__iter__()
        pkg = pkg_iter.next()
        for block in proc.stdout.read().split("\n\n"):
            date_match = date_re.search(block)
            path_match = path_re.search(block)
            if date_match and path_match:
                date = date_match.group(1)
                path = path_match.group(1)
                while pkg.path != path:
                    # Should never raise StopIteration
                    pkg = pkg_iter.next()
                # Use UTC internally
                pkg.last_checked = dateparser.parse(date).astimezone(tz.tzutc())

    def _update_metadata(self):
        for pkg in self:
            metadata_path = os.path.join(self.workdir, os.path.dirname(pkg.path), "metadata.xml")
            cpes = get_cpes(metadata_path)
            pkg.add_cpes(cpes)

    def _update_deb_suffixes(self):
        dico = {}
        for spec in glob.glob(os.path.join(self.workdir,"specs","clip*","*.xml")):
            first=spec.find("specs/")+6
            last=spec.find("/",first)
            specie=spec[first:last]
#recuperer la variable CLIP_SPEC_DEFINES de /etc/clip_build.conf
            stringtab=filter(lambda x: not re.search('^#',x),\
            subprocess.check_output(["cpp",spec]).split('\n'))
            try:
#outch there may be more than one spec file per directory
                if dico.has_key(specie):
                    dico[specie].append(etree.fromstring("".join(stringtab)))
                else:
                    dico[specie]=[etree.fromstring("".join(stringtab))]
            except :
                pass
        for pkg in self:
            suffixes = get_suffix(dico,pkg)
            pkg.add_deb_suffixes(suffixes)



    def _update_deb_priority(self):
        dico = {}
        for spec in glob.glob(os.path.join(self.workdir,"specs","clip*","*.xml")):
            first=spec.find("specs/")+6
            last=spec.find("/",first)
            specie=spec[first:last]
#recuperer la variable CLIP_SPEC_DEFINES de /etc/clip_build.conf
            stringtab=filter(lambda x: not re.search('^#',x),\
#            subprocess.check_output(["clip-specpp","-i",spec,"-o","/dev/stdout"]).split('\n'))
            subprocess.check_output(["cpp",spec]).split('\n'))
            try:
#outch there may be more than one spec file per directory
                if dico.has_key(specie):
                    dico[specie].append(etree.fromstring("".join(stringtab)))
                else:
                    dico[specie]=[etree.fromstring("".join(stringtab))]
            except :
                pass
        for pkg in self:
            priority = get_package_deb_priority(dico,pkg)
            pkg.add_priority(priority)


    def _update_slot(self):
        dummy=open("/dev/null",'wb')
        sys.stdout.flush()
        sys.stderr.flush()
        save_fd1=os.dup(sys.stdout.fileno())
        save_fd2=os.dup(sys.stderr.fileno())
        os.dup2(dummy.fileno(),1)
        os.dup2(dummy.fileno(),2)
        for pkg in self:
           d = portage.db[portage.root]["porttree"].dbapi
           try:
               pkg.slot = d.aux_get(pkg.af, ["SLOT"])[0]
           except:
                pkg.broken="true"
                #execption here destoy the portage object
                d = portage.db[portage.root]["porttree"].dbapi
                pass
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(save_fd1,1)
        os.dup2(save_fd2,2)
        os.close(save_fd1)
        os.close(save_fd2)
        dummy.close()

    def _update_visible(self):
        d = portage.db[portage.root]["porttree"].dbapi
        for pkg in self:
            if len(d.xmatch('match-visible', pkg.af)) == 0:
                pkg.masked="true"

    def scan(self):
        if self.workdir is None:
            raise Exception("Missing workdir, are you in the SDK?")
        new_pkgs = PackageDb(None)
        new_pkgs._update_ebuild()
        new_pkgs._update_vcs()
        new_pkgs._update_metadata()
        new_pkgs._update_slot()
        new_pkgs._update_visible()
        new_pkgs._update_deb_suffixes()
        new_pkgs._update_deb_priority()
        new_pkgs._refresh()
        for pkg in new_pkgs:
            match = self._get_section(pkg._section)
            if match is None:
                pkg._extra = []
            else:
                pkg._extra = match._extra
                # Do not update the DB date if the stored date is still newer
                if match.last_checked is not None and (pkg.last_checked is None or match.last_checked > pkg.last_checked):
                    pkg.last_checked = match.last_checked
                # Only add new CPEs
                pkg.add_cpes(match.cpes)
        self._db = new_pkgs._db

    def search_names(self, names):
        for pkg in self._db:
            if pkg.name in names:
                yield pkg

    def match(self, dep):
        return portage.dep.match_from_list(dep, [p.af for p in self._db])

    # ------------------------------------------------------------
    # for a given debian package name
    # return the list of corresponding pkg object from clip-pkgdb
    # species = "clip-rm", "cip-gtw", "clip-bare"
    #
    def getPkgObjFromDeb(self, deb_name, species,casesensitive=False):
        pkg_in_clippkgdb_list=[]

        # split par "_" pour extraire numéro de version
        split_underscore=deb_name.split("_")

        if (len(split_underscore) < 3):
            print "erreur de split _ : moins de 3 parties"
            return []

        version_number=split_underscore[len(split_underscore)-2]
        name_parts=split_underscore[:len(split_underscore)-2]
        name="".join(name_parts)

        if (not casesensitive):
            name=name.upper()
            version_number=version_number.upper()

        # recherche du pkg dans pkgdb qui correspond au début du nom obtenu par split "_"
        for pkg in self._db:
            pkg_name_to_compare=""
            version_number_to_compare=""

            if casesensitive :
                pkg_name_to_compare=pkg.name
                version_number_to_compare=str(pkg.version_ebuild)
            else :
                pkg_name_to_compare=pkg.name.upper()
                version_number_to_compare=str(pkg.version_ebuild).upper()

            if (name == pkg_name_to_compare) and (version_number == version_number_to_compare):
                # if there is no suffix and that name and version match
                pkg_in_clippkgdb_list.append(pkg)
                break

            if (version_number != version_number_to_compare):
                continue

            # try to find the pkg.name in the deb name
            pos=name.find(pkg_name_to_compare)
            if (pos != 0):
                print "same version number but can't find name "+name+" at the beginning of package name : "+pkg_name_to_compare
                continue

            # if the pkg.name is in the deb name then get the potential suffix
            # which is after the pkg.name
            potential_suffix=name[len(pkg.name):]

            for key in pkg.deb_suffixes.keys():
                if species in key:
                    suffix_list=pkg.deb_suffixes[species]

                    if (not casesensitive):
                        suffix_list=map(lambda input : input.upper(), suffix_list)

                    if potential_suffix in suffix_list:
                        pkg_in_clippkgdb_list.append(pkg)
                        break

        return pkg_in_clippkgdb_list


def get_atom_dependencies(atom, db=None, all_useflags=False):
    if db is None:
        db = portage.db[portage.root]["porttree"].dbapi
    if atom != "":
        return portage.dep.use_reduce(portage.dep.paren_enclose(db.aux_get(atom, ["DEPEND", "RDEPEND"])), matchall=all_useflags)
    return []

def get_atom_uris(atom, db=None):
    if db is None:
        db = portage.db[portage.root]["porttree"].dbapi
    if atom != "":
        return db.getFetchMap(atom)
    return OrderDict()

class PkgFound(str):
    pass

class PkgNotFound(str):
    pass

def get_all_dependencies(depends, db=None, pkgs=None, all_useflags=False, exclude=set()):
    if db is None:
        db = portage.db[portage.root]["porttree"].dbapi
    if pkgs is None:
        pkgs = PackageDb(None)
    for dep in depends:
        if isinstance(dep, list):
            for sub in get_all_dependencies(dep, db, pkgs, all_useflags, exclude):
                yield sub
            continue
        if dep.startswith("!"):
            continue
        if dep == u"||":
            continue
        pkgs_deps = pkgs.match(dep)
        if pkgs_deps:
            # Assume we have all the dependencies (i.e. use flags) for our packages
            exclude.update([PkgFound(p) for p in pkgs_deps])
            continue
        atom = db.xmatch("bestmatch-visible", dep)
        if atom == "":
            atom = PkgNotFound(dep)
        else:
            atom = PkgFound(atom)
        if atom in exclude:
            continue
        exclude.add(atom)
        yield atom
        if isinstance(atom, PkgNotFound):
            continue
        for sub in get_all_dependencies(get_atom_dependencies(atom, db, all_useflags), db, pkgs, all_useflags, exclude):
            yield sub

def _clean_permissions(dst):
    for root, dirs, files in os.walk(dst):
        for name in files:
            os.chmod(os.path.join(root, name), 0600)

def export_package(pkg, dst, distfiles_mirror, db=None, dry_run=False):
    if db is None:
        db = portage.db[portage.root]["porttree"].dbapi
    src = db.findname(pkg)
    if src is None:
        raise Exception("Can't find ebuild {}".format(pkg))
    pkg_src = os.path.dirname(src)
    pkg_atom = os.path.sep.join(pkg_src.split(os.sep)[-2:])
    pkg_dst = os.path.join(dst, PORTAGE_BASENAME, pkg_atom)
    if os.path.exists(pkg_dst):
        print("Package exists, removing it: {}".format(pkg_dst))
        if not dry_run:
            shutil.rmtree(pkg_dst)
    print("pkg_cp {} -> {}".format(pkg_src, pkg_dst))
    if not dry_run:
        shutil.copytree(pkg_src, pkg_dst, symlinks=True)
        _clean_permissions(pkg_dst)

    dst = os.path.join(dst, DISTFILES_BASENAME)
    if not dry_run:
        try:
            os.makedirs(dst)
        except:
            pass
    for distfile in get_atom_uris(pkg, db):
        dist_src = "{}/{}".format(distfiles_mirror, distfile)
        dist_dst = os.path.join(dst, distfile)
        if os.path.exists(dist_dst):
            print("Distfile exists, keeping it: {}".format(dist_dst))
            continue
        print("dist_cp {} -> {}".format(dist_src, dist_dst))
        if not dry_run:
            try:
                res = urllib2.urlopen(dist_src)
            except Exception as e:
                raise Exception("Failed to get {} : {}".format(dist_src, e))
            with open(dist_dst, "wb") as f:
                f.write(res.read())

# To call before any portage use, if needed
def init_portage(portage_path, profile=None):
    portage_path = os.path.abspath(portage_path)
    if profile is None:
        for p in PORTAGE_PROFILES:
            profile_path = os.path.join(portage_path, "profiles", p)
            if os.path.exists(profile_path):
                profile = p
                break
        if profile is None:
            raise Exception("Could not find a profile in {}".format(portage_path))
    else:
        profile_path = os.path.join(portage_path, "profiles", profile)
        if not os.path.exists(profile_path):
            raise Exception("Profile directory does not exist: {}".format(profile_path))
    os.environ["PORTDIR"] = portage_path
    portage.const.PROFILE_PATH = profile_path
    # PORTAGE_CONFIGROOT: Virtual root to find configuration (e.g. etc/make.conf)
    #os.environ["PORTAGE_CONFIGROOT"] = WORKDIR

# ------------------------------------------------------------
# take the complete path to a spec file
# return the input for clip-compile "clip-rm/clip" "clip-rm/rm" ...
def getSpecFileShortName(spec_file_path):
    pos_start=spec_file_path.rfind("clip-")
    pos_end=spec_file_path.find(".spec.xml")
    return spec_file_path[pos_start:pos_end]

