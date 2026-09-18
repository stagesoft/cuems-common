# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
#
# equivs template for a STUB cuems-nodeconf at a PRE-CUTOVER version (0.1.0-7),
# instantiated by tests/packaging/release-gate-demo.sh (@VERSION@ substituted).
# Mirrors the real package's CUEMS relationships as of ../cuems-nodeconf 478bc49
# ("release: cuems-nodeconf 0.1.0-7"): a floor on cuems-utils, a floor on
# cuems-common, and NO Breaks — this is the version that knows only the retired
# discovery key. Its other dependencies (python3-zeroconf, avahi-daemon, ...) are
# left out deliberately: only the relationships under test are reproduced.
Section: misc
Priority: optional
Standards-Version: 4.6.0

Package: cuems-nodeconf
Version: @VERSION@
Maintainer: CUEMS release-gate demonstration <noreply@stagelab.coop>
Architecture: all
Depends: cuems-utils (>= 0.1.0rc5), cuems-common (>= 1.0.0)
Description: STUB pre-cutover cuems-nodeconf for the release-gate demonstration
 Built by tests/packaging/release-gate-demo.sh inside a disposable environment.
 It provides no daemon; it exists so dpkg and apt can be watched judging the
 Breaks that cuems-common declares against an un-renamed cuems-nodeconf.
