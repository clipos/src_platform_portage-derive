# Tool to help keep a Portage tree up-to-date

Set of tools to automate Portage tree management

This is designed to be used in a Gentoo-based SDK.

To get help, run `portage-derive --help`.

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
portage-derive -p . equalize
git add -A
git commit "--message=Merge branch 'upstream' into autoclean"

# Merge with our custom changes
git checkout master
git merge autoclean

# Manually deal with the remaining merge conflicts, if any
```
