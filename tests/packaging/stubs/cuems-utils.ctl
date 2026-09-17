# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
#
# equivs template for a STUB cuems-utils, instantiated per version by
# tests/packaging/release-gate-demo.sh (@VERSION@ is substituted). Only the
# version relationship is under test, so the stub carries nothing but a version
# and the one path cuems-common's postinst requires before it will configure:
# /usr/lib/cuems/bin/python3 (debian/postinst exits 1 without it).
Section: misc
Priority: optional
Standards-Version: 4.6.0

Package: cuems-utils
Version: @VERSION@
Maintainer: CUEMS release-gate demonstration <noreply@stagelab.coop>
Architecture: all
Depends: python3
Links: /usr/bin/python3 /usr/lib/cuems/bin/python3
Description: STUB cuems-utils for the release-gate demonstration — not the real package
 Built by tests/packaging/release-gate-demo.sh inside a disposable environment.
 It provides no library; it exists so dpkg and apt can be watched judging the
 version relationships cuems-common declares against cuems-utils.
