# Tool to help keep a Portage tree up-to-date

Set of tools to automate Portage tree management

This is designed to be used in a Gentoo-based SDK.

To get help, run `portage-derive --help`.

## Refresh metadata information for the Portage tree

When not using a Portage tarball nor rsync (i.e. using Git), you may need to rebuild metadata information for the Portage tree with `egencache --update "--jobs=$(($(nproc) + 1))"`.
These files are in the *metadata/md5-cache* directory from the portage tree.
Regenerating this cache may takes some time.

## Portage tree merge workflow

```bash
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
