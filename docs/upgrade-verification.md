<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Upgrade verification — the checks tests cannot make

The repository's tests cover the migration tools, the templates, the sudoers files, the ordering of
`postinst` and the version bounds. They cannot cover a running host: the discovery daemon, the
role-flip privilege, the conffile prompts, and a real cluster finding itself again. This procedure
covers those (constitution, Testing Gate). **Perform it on a controller plus at least one node**,
and keep the record sheet at the end.

The out-of-order installation refusals are demonstrated separately and reproducibly by
`tests/packaging/release-gate-demo.sh`; its output is
`specs/001-node-role-and-conversion-ordering/evidence/out-of-order-refusal.txt`.

**When**: after the coordinated merge of this feature with `cuems-nodeconf`'s discovery cutover —
both halves must be installed together — and never mid-show. The cluster is upgraded as a unit
(`docs/upgrade-ordering.md` §3).

---

## 1. Before upgrading — on every host

Record versions, and audit by file as well as by the package database: on hosts deployed by file
copy the database can be stale (`CLAUDE.md`, dpkg-db drift).

```sh
dpkg-query -W -f='${Package} ${Version} ${db:Status-Abbrev}\n' cuems-common cuems-utils cuems-nodeconf
ls -l --time-style=long-iso /usr/share/cuems/cuems.service.* /usr/bin/cuems-migrate-*
```

Save the live state **outside** `/etc` so nothing the upgrade does can touch the copy:

```sh
sudo mkdir -p /root/pre-upgrade
sudo cp -a /etc/cuems/network_map.xml /etc/avahi/services/cuems.service /etc/sudoers.d /root/pre-upgrade/
```

## 2. The `network_map.xml` conffile prompt — answered both ways

`/etc/cuems/network_map.xml` is a conffile. dpkg asks about it only when the shipped version changed
since the installed one **and** the local copy was modified. This release changes the shipped
version, so **every host whose map was edited is prompted**. A host whose copy was never modified
gets the new version **silently, with no prompt**.

Across the two hosts, answer the prompt **differently**: keep-local on one, take-maintainer on the
other.

| Answer | Live map afterwards | The other copy |
|---|---|---|
| **Keep your currently-installed version** (`N`, the default) | the operator's topology, converted to `node_role` by `postinst` | the maintainer's version at `network_map.xml.dpkg-dist` |
| **Install the package maintainer's version** (`Y`) | the shipped map: an **empty** `<node_list/>` — no nodes | the operator's topology at `network_map.xml.dpkg-old`, **already converted** by `postinst` |

On the take-maintainer host, restore the topology — it is a copy, because `postinst` converted
`.dpkg-old` — then validate it:

```sh
sudo cp -a /etc/cuems/network_map.xml.dpkg-old /etc/cuems/network_map.xml
```

<!-- validate-command -->
```sh
/usr/lib/cuems/bin/python3 -c "import sys, xmlschema; xmlschema.XMLSchema11(sys.argv[1]).validate(sys.argv[2])" /etc/cuems/network_map.xsd /etc/cuems/network_map.xml
```

Silence and exit status 0 mean the map is valid. On failure the command prints the first
violation and exits 1. It uses the `xmlschema` library of the `cuems-utils` venv, which every CUEMS
host has; do **not** use `xmllint`, which no dependency of this package installs and which cannot
evaluate the XSD 1.1 assertions this ecosystem's schemas use
(`dev/planning/xmllint-runtime-dependency.md`). Compare the restored map with
`/root/pre-upgrade/network_map.xml`: the content is the same, with `<node_type>` rewritten to
`<node_role>` if the host was upgraded from before that rename.

## 3. Discovery — on every host

The live announcement uses the new key, and a backup of the old file sits beside it:

```sh
grep -n txt-record /etc/avahi/services/cuems.service    # node_role=controller|node|firstrun, twice
ls -1 /etc/avahi/services/                              # cuems.service and cuems.service.<timestamp>.bak
```

The upgrade prints one of: `converted: … backup at …`, `already current: …`, `absent: …` or
`refused: … — <reason>`. A `refused` host needs its file fixed by hand as the message says, then:

```sh
sudo /usr/bin/cuems-migrate-avahi-service
```

What the network sees (`avahi-browse` is in the `avahi-utils` package, which is not a dependency):

```sh
avahi-browse -rt _cuems_nodeconf._tcp     # every host resolves with txt = ["node_role=…" "uuid=…"]
```

**SC-001**: the controller lists the node, and the node finds the controller.

## 4. The role-flip privilege — on a pristine and on a locally modified sudoers host

The privilege moved from `/etc/sudoers.d/99-cuems` to `/etc/sudoers.d/99-cuems-avahi`. Check it
without executing anything:

```sh
sudo -l -U cuems /usr/bin/cp /usr/share/cuems/cuems.service.node /etc/avahi/services/cuems.service
sudo -l -U cuems /bin/systemctl reload avahi-daemon.service
sudo visudo -c
ls -1 /etc/sudoers.d/
```

Both `sudo -l` lines print the command (allowed). `visudo -c` parses everything. `99-cuems` is gone —
on a host where it had been edited it is kept as `99-cuems.dpkg-bak`, which sudo ignores because the
name contains a dot. Do at least one host whose `99-cuems` had been locally modified (**SC-004**).

## 5. A node whose map names no controller (**SC-015**)

On a node before its map is provisioned (or on the take-maintainer host before restoring):

```sh
systemctl --failed                                   # neither chrony nor systemd-journal-upload listed
journalctl -b -u chrony -u systemd-journal-upload | grep WARNING
```

Each logs a warning naming the map; chrony runs with no cluster time source and the journal
uploader is skipped. This is the designed outcome (`docs/upgrade-ordering.md` §4); provisioning the
map from `/usr/share/doc/cuems-common/network_map.xml.example` and restarting both ends it.

## 6. What the upgrade does not touch — project libraries

**A CUEMS upgrade never rewrites an operator's project documents.** The batch conversion of project
documents (`cuems-convert-documents`) is an operator command owned by `cuems-utils`, not something
this package runs. A library nobody converts keeps loading, because `cuems-utils` converts an old
document in memory when it reads it. Running the batch conversion is a choice for a moment the
operator picks; consult `cuems-utils`' own documentation for it. Confirm on the controller that no
project file under the library changed its modification time during the upgrade.

## 7. Orderly cluster power-off — fixed in this candidate, verified over there

This was a **known issue** while it lasted: `cuems-cluster-poweroff` selects its targets through
`cuems-power-bridge`, whose parser filtered on the retired `node_type` vocabulary that this
package's own conversion removes from `network_map.xml`. The selection matched nothing, so the
controller powered itself off, armed the Shelly and cut mains with every node still running —
and reported success.

**It is fixed in this candidate.** `cuems-power-bridge` replaced that parser with the owning
library's reading path, and the selection in `cuems-cluster-poweroff` now comes from the bridge's
own topology adapter, so this hook and `POST /shutdown` cannot disagree about a cluster. Both
halves land together: `cuems-common` 1.3.0-23 and `cuems-power-bridge` 0.3.1-1, under the shared
`xml-refactor-merge-candidate` tag, with a reciprocal `Breaks:` pair so a mixed pair is refused
rather than discovered part-way through a poweroff.

**Do not re-verify it from here.** The checks that need a real cluster live on one ledger in the
repository that owns the code:

> `cuems-power-bridge`:
> `specs/002-cluster-poweroff-cli/checklists/hardware-verification.md`

Its §4 (power-off selects the adopted nodes), §5 (the boot readiness gate, verified
**separately**) and §6 (an unconverted map must refuse and leave mains on) are the checks that
retire this section. That ledger carries its own per-host record sheet and is meant to be worked
in the same pass as this document and as `cuems-nodeconf`'s ledger.

**What remains this document's business**: the conversion itself (§2), discovery (§3) and the
privilege flip (§4) — the inputs the bridge then reads.

## 8. Hosts the package manager never configures (file-copy deployment)

On a host where packages are deployed by copying extracted files, **no maintainer script runs**, so
do by hand what `preinst`/`postinst` do in this release, in this order:

1. Convert the network map, and any copies left beside it:
   ```sh
   for f in /etc/cuems/network_map.xml /etc/cuems/network_map.xml.dpkg-dist /etc/cuems/network_map.xml.dpkg-old; do
       [ -f "$f" ] && sudo /usr/bin/cuems-migrate-network-map "$f"
   done
   ```
2. Migrate the live discovery file:
   ```sh
   sudo /usr/bin/cuems-migrate-avahi-service
   ```
3. Install the new sudoers file first, then move the old one aside to a dotted name, then check:
   ```sh
   sudo install -m 0440 -o root -g root <extracted>/etc/sudoers.d/99-cuems-avahi /etc/sudoers.d/99-cuems-avahi
   sudo mv /etc/sudoers.d/99-cuems /etc/sudoers.d/99-cuems.retired
   sudo visudo -c
   ```
4. Pick up the changed units and reload the discovery daemon:
   ```sh
   sudo systemctl daemon-reload
   sudo systemctl reload avahi-daemon.service
   ```

Then run §3–§5 on that host as on any other.

---

## Record sheet

Copy once per host.

```
host:                     role (controller/node):
date:                     operator:
versions before:          cuems-common      cuems-utils      cuems-nodeconf
versions after:           cuems-common      cuems-utils      cuems-nodeconf
network_map prompt:       [ ] none (unmodified)  [ ] keep-local  [ ] take-maintainer
  restored from .dpkg-old and validated:  [ ] n/a  [ ] yes
discovery file outcome:   [ ] converted  [ ] already current  [ ] absent  [ ] refused → fixed by hand
avahi-browse shows node_role:             [ ] yes
role-flip privilege (sudo -l, both):      [ ] yes      99-cuems had been modified: [ ] yes [ ] no
visudo -c:                                [ ] parsed OK
no-controller check (node, if applicable): chrony not failed [ ]  journal-upload not failed [ ]
cluster topology intact (SC-001):          controller lists node [ ]  node finds controller [ ]
project library untouched:                 [ ] yes
notes:
```
