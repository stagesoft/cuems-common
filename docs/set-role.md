<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
-->

# `cuems-set-role`: controller or node

One image serves both roles. A box is born a standalone controller; this command
gives it either role, as often as needed.

```
sudo cuems-set-role controller [--hostname NAME]
sudo cuems-set-role node ADDRESS [--controller ADDRESS] [--hostname NAME]
cuems-set-role node 169.254.0.11 --dry-run      # what would change
```

`ADDRESS` is the node's own address on the cluster link, `169.254.0.11` to
`169.254.0.26`: the addresses the SSH jump through the controller allows. The
controller's address on that link is `169.254.0.1`.

**It changes nothing that is running.** It writes files and switches units on
and off, and asks for a reboot. The one thing it stops is
`cuems-controller.path`, before it creates `master.lock`: systemd watches that
file and would start the controller there and then. Avahi reads its service
record when it changes, so the box announces its new role at once.

It refuses while a project is loaded (`/tmp/cuems.show.lock`, exit 6), before
the first boot has finished, and, for a node, on a box with no identity. It is
safe to run twice. It does not use `cuems-nodeconf`. No package script runs it.

## What each role gets

| | controller | node |
|---|---|---|
| `/etc/cuems/master.ip`, `master.lock` | present | absent |
| Units on | node target; controller target, both controller services, power bridge and cluster power-off where installed; journal collector | node target; journal upload |
| Units off | journal upload, nodeconf | controller target, editor, power bridge, cluster power-off, journal collector, nodeconf; **`cuems-controller-engine` masked** |
| `/etc/network/interfaces` | `ethernet1` static `169.254.0.1/16`; an existing `bond0` stanza is kept | `bridge0` over both wired ports with the node's address; no gateway; Wi-Fi left down |
| `/etc/hosts` | `controller.local` is the box itself | `controller.local` is the controller's link address |
| Avahi record | controller | node |
| `network_map.xml`, own node | master, `127.0.0.1`, `role_id` `controller` | slave, its address, `role_id` `node01`…`node16` from the address (`.11` is `node01`) |

The interfaces file it replaces is kept as
`/etc/network/interfaces.cuems-before-set-role`. On a node, an unowned copy of
rtpmidid's `cuems-node-group.conf` under `/etc` is set aside: it hides the
packaged one.

**Why the engine is masked.** The engine package enables and starts both
engines on whatever box it is installed on. With the unit masked, that step of
the install only prints warnings ("Failed to enable", "Failed to start") and
the install goes on. Going back to controller unmasks it. A copy of that unit
under `/etc/systemd/system` prevents masking, and the command says so.

## The name

`--hostname` writes the host name, the `127.0.1.1` line, an Avahi `host-name=`
line if there is one, and `<hostname>` in the box's own map entry, in one run.
**Rename a box only this way:** the engine names the fade target by the map and
gradient-motiond filters on the host name, so any other rename drops every fade
with no error. Without `--hostname` the box keeps its name.

Nodes find their controller by `controller.local`, which their `/etc/hosts`
pins to its link address, so the controller may have any name. Whoever looks for
`controller.local` **on the site's LAN** (a browser, a power relay) does not
find a controller named otherwise.

## What is left to do by hand

- **Put the cluster together.** The command knows one box. A new node's map has
  a placeholder controller (uuid all zeros, alias "controller (not listed
  yet)"), there only so that log upload and the time source find an address.
  List each node in the controller's `network_map.xml` and
  `default_mappings.xml`, and put the controller's real entry in the node's map.
- On a controller going back from a node with `NET_MODE` `cable-static` or `ap`,
  run `cuems-net-mode` again after the reboot (the command says so).
- Outputs, Wi-Fi name and passphrase, passwords: commissioning.

## The state a box is born in

A box is born with the controller form of everything above. **The image recipe
gets there by running `cuems-set-role controller`** during the install, while
the box has no identity yet (the one case where that is allowed). So going to
node and back returns the box to the state it was born in.
