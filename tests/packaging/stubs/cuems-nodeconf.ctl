# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
#
# equivs template for a STUB cuems-nodeconf, instantiated per version by
# tests/packaging/release-gate-demo.sh (@VERSION@ is substituted). Its only
# relationship mirrors the real package's today (../cuems-nodeconf/debian/control:19):
# cuems-common (>= 1.0.0) — the floor that does NOT refuse an un-renamed
# cuems-common, which the demonstration records as the reverse-edge gap.
Section: misc
Priority: optional
Standards-Version: 4.6.0

Package: cuems-nodeconf
Version: @VERSION@
Maintainer: CUEMS release-gate demonstration <noreply@stagelab.coop>
Architecture: all
Depends: cuems-common (>= 1.0.0)
Description: STUB cuems-nodeconf for the release-gate demonstration — not the real package
 Built by tests/packaging/release-gate-demo.sh inside a disposable environment.
 It provides no daemon; it exists so dpkg and apt can be watched judging the
 Breaks that cuems-common declares against cuems-nodeconf.
