# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
#
# equivs template for a STUB cuems-nodeconf at the RENAMED version (0.1.0-8),
# instantiated by tests/packaging/release-gate-demo.sh (@VERSION@ substituted).
# Mirrors the real package's CUEMS relationships as of ../cuems-nodeconf — the
# bounded cuems-utils, the cuems-common floor, and the reverse half-rename guard
# `Breaks: cuems-common (<< 1.3.0-23~)` added there in 8ce7552. That guard is
# what makes the reverse direction refusable: without it, a renamed daemon
# installs beside an un-renamed cuems-common and discovery silently finds
# nothing. Other dependencies are left out: only the relationships under test.
Section: misc
Priority: optional
Standards-Version: 4.6.0

Package: cuems-nodeconf
Version: @VERSION@
Maintainer: CUEMS release-gate demonstration <noreply@stagelab.coop>
Architecture: all
Depends: cuems-utils (>= 0.1.0rc16), cuems-utils (<< 0.1.1~), cuems-common (>= 1.0.0)
Breaks: cuems-common (<< 1.3.0-23~)
Description: STUB renamed cuems-nodeconf for the release-gate demonstration
 Built by tests/packaging/release-gate-demo.sh inside a disposable environment.
 It provides no daemon; it exists so dpkg and apt can be watched judging the
 Breaks in both directions of the discovery cutover.
