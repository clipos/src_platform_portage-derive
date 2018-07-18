# A tool to link metadata to packages in a standalone text database optimized for version control systems

## Setting the portage directory

portage is currently a symlink in the source directory. It should point to a
working portage install. If you don't have a system-wide portage install,
you can remove the symlink and create a portage directory that contains the
portage sources instead.

## Manual installation

You can use the "make" command to install clip-pkgdb.

## Building a Debian/Ubuntu package

Just run dpkg-buildpackage from the source directory. A .deb will be ready in the parent directory.

## How to use

TBD
