# Tool to help keep a Portage tree up-to-date

This tool is designed to be used in a Gentoo-based SDK.

To get help, run `portage-derive --help`:
```
usage: portage-derive [-h] [-n] -p PORTDIR [-q] [-v] {list,shell,equalize} ...

Tool to automate Portage tree management.

positional arguments:
  {list,shell,equalize}
    list                list visible packages
    shell               launch an IPython shell to hack with the Portage tree
                        database
    equalize            equalize a Portage tree (make it Git-friendly to ease
                        merges with stable ebuild names and their symlinks)

optional arguments:
  -h, --help            show this help message and exit
  -n, --dry-run         do not perform any action on the file system
  -p PORTDIR, --portdir PORTDIR
                        Portage tree directory
  -q, --quiet           do not output anything except errors
  -v, --verbose         print debug informations
```

## Refresh metadata information for the Portage tree

When not using a Portage tarball nor rsync (i.e. using Git), you may need to rebuild metadata information for the Portage tree with `egencache --update "--jobs=$(($(nproc) + 1))"`.
These files are in the `metadata/md5-cache` directory from the Portage tree.
Regenerating this cache may take some time.

## Equalizing a Portage tree

Portage handles overlays to mask a set of packages.
Handling package modifications implies to manually synchronize upstream ebuilds with our owns, which may be time consuming and error-prone.
Git merges can be leveraged to automate the synchronization of most of the changes from an upstream branch (Gentoo).
However, because of the ebuild naming convention, each version of an ebuild is a dedicated file.
This makes it difficult to keep track of our modifications, and may disturb Git's file tracking.
The tool `portage-derive equalize` helps overcome this issue.

Equalizing a Portage tree means two things:
- only keep the best ebuilds (for each slots) which are visible to our Portage profile;
- using a stable naming convention to ease file tracking (and merging).

This stable naming convention consists of identifying the best ebuild for each slot, starting from the latest (higher version), with a numbering independent from the version and the slot.
The name template looks like this: `.<package-name>.ebuild.<id>`.
The `<id>` starts at 0 and is increased for each previous visible slot.
Starting with the most up-to-date makes sense because, most of the time, it is the one you are using and are willing to modify.
This way, when a new version or a new slot is made visible by upstream, our modification on the last (stable) ebuild will still be in the `.<package-name>.ebuild.0` file.
To make Portage work as usual we need to keep all ebuilds tied to a specific version, which is done with symlinks pointing to the equalized ebuilds.
This symlinks keep track of the original ebuild file names and are well handled by Git merges.

This mechanism does not replace Portage overlays.
Overlays are useful to manage independent packages in standalone repositories.
Moreover, this may be used to enforce custom access controls on these repositories.

## Portage tree merge workflow

There are three main Git branches:
- *upstream*: keep track of the upstream (e.g. Gentoo) master branch;
- *autoclean*: used to clean stuff (e.g. equalize) in an automatic way;
- *master*: based on autoclean and includes ebuild modifications.
    This branch should be the only one used in an SDK.

The autoclean and master branches must be a fork of the upstream branch.
Then, the following workflow can be used to update the master branch.

```bash
# Go to a clean (see git status) Portage tree
cd /path/to/portage/tree

# Update Gentoo's tree
git checkout upstream
git pull

# Artificial merge to keep track of the Git history
git checkout autoclean
git merge --no-commit --strategy=ours upstream
git read-tree -u -m upstream
egencache --update "--jobs=$(($(nproc) + 1))"
portage-derive -p . equalize
git add -A
git commit "--message=Merge branch 'upstream' into autoclean"

# Merge with our custom changes
git checkout master
git merge autoclean

# Manually deal with the remaining merge conflicts, if any
```
