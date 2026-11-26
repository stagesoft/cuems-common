<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
-->

# The first boot of a box written from the base image

One image serves every box, so it holds no identity: no keys, no certificate,
no uuid, no name. The first boot makes them. It runs only while
`/var/lib/cuems/firstboot.armed` exists, and **only the step that seals an image
creates that file**. Installing or upgrading cuems-common never arms a box, and
on an unarmed box none of this does anything.

## While armed, the box boots only this

A systemd generator (`cuems-firstboot-generator`) makes
`cuems-firstboot.target` the default target of every armed boot. That target
pulls in the basic system and `cuems-firstboot.service`, nothing else: no
CUEMS service, no network configuration, no DHCP server, no access point, no
mDNS. A box without an identity cannot disturb the network it is plugged into.

The basic system still brings udev, timers and sockets, so some things are told
to stay quiet while armed: `cuems-net-guard` leaves at once, and the Avahi
service and socket, `networking.service` and `ifup@.service` (which udev starts
for an `allow-hotplug` interface) have a condition. **A new unit of this package that is wanted by
`timers.target`, `sockets.target`, `paths.target` or `sysinit.target` runs on an
armed box**: give it the same guard if it can touch the network or needs an
identity.

## What it does, in order

1. **SSH host keys**, if the box has none.
2. **Is the box new?** It is refused when `settings.xml` holds a uuid that
   neither the seed nor an earlier try chose, when the library holds a project,
   or when a first boot already finished here.
3. **Platform settings** (`cuems-platform apply`, see `platform-profiles.md`).
4. **Identity.** The uuid comes from the seed file, or is a new uuid4. It is
   saved in `/var/lib/cuems/firstboot.state` before any document changes. `mac`
   is the permanent address of the port that becomes `ethernet0`. It is written
   to `settings.xml`, `network_map.xml` (own node: `<ip>127.0.0.1</ip>` and
   `<hostname>`), `default_mappings.xml` (the platform's starting file, only
   when the box has none), the three Avahi templates, and the Avahi record of a
   standalone controller.
5. **Name:** the hostname is the 12 hex digits of that mac. `/etc/hosts` gets
   the `127.0.1.1` line and `127.0.0.1 controller.local`.
6. Enables `cuems-gradient-motiond`.
7. **Web certificate** and, with `cuems-power-bridge` installed, its SSH key.
8. **Grows the root partition** to the whole disk.
9. Writes `/var/lib/cuems/firstboot.json`, removes the seed and the arming file,
   logs `done platform=… uuid=…` and **reboots**.

The machine-id is made by systemd, from an empty `/etc/machine-id`.

## The three ways it ends

| Result | Exit | What the box does |
|---|---|---|
| done | 0 | disarms and reboots into its normal target |
| refused (not new) | 10 | changes nothing of its own (it may add SSH host keys if it had none), disarms and goes on to its normal target |
| failed | 1 | stays armed, **no reboot**; `cuems-firstboot-rescue` asks for DHCP on every wired port, starts SSH and a console, and prints where the report is |

After a failure, fix the cause and reboot: it goes on with the same uuid. SSH
takes keys only, as on any CUEMS box. For an unknown platform, or ports that do
not fit the profile's rule, the packaged `.link` files are renamed to
`*.link.cuems-disabled` before the rescue.

## The seed: keeping an identity across a re-image

To give a re-written box the uuid it had, put a file on the **EFI partition**
before its first boot:

- path: `/boot/efi/cuems-seed.txt` (`cuems-seed.txt` at the root of that
  partition);
- content: the uuid and nothing else;
- the first boot removes it when it has finished.

A seed that cannot be read as one real uuid is a failure, never a new identity.
Put the project library back only **after** the first boot has finished: a box
with a project is refused.

## What sealing an image must leave

This is the contract with whatever makes the image.

| Item | State |
|---|---|
| `/var/lib/cuems/firstboot.armed` | created, last |
| `/var/lib/cuems/firstboot.state`, `.json` | absent |
| `/etc/cuems/settings.xml` | the template of the installed cuems-utils, with the uuid `00000000-0000-0000-0000-000000000000` and the mac `REPLACE-WITH-NODE-MAC` |
| `/etc/cuems/network_map.xml` | one node, in the shape below. **The file cuems-common ships does not match the released schema** and cannot be used |
| `/etc/cuems/default_mappings.xml`, `/etc/avahi/services/cuems.service` | absent |
| `/usr/share/cuems/cuems.service.*` | as packaged (sentinel uuid) |
| SSH host keys, TLS key and certificate, power-bridge key | absent |
| `/etc/machine-id` | empty |
| `/etc/hostname` | `localhost` |
| packages | `cloud-guest-utils`, `gdisk`, `isc-dhcp-client` and `openssh-server` installed |
| disks | root is ext4 and the last partition, with no separate `/var` (the arming file must be readable before anything is mounted); the EFI partition is mounted at `/boot/efi` |

```xml
<cms:CuemsNetworkMap xmlns:cms="https://stagelab.coop/cuems/">
    <node_list>
        <node>
            <uuid>00000000-0000-0000-0000-000000000000</uuid>
            <mac>REPLACE-WITH-NODE-MAC</mac>
            <name>REPLACE-WITH-NODE-MAC._cuems_nodeconf._tcp.local.</name>
            <node_type>NodeType.master</node_type>
            <ip>127.0.0.1</ip>
            <adopted>True</adopted>
            <online>True</online>
        </node>
    </node_list>
</cms:CuemsNetworkMap>
```

## Limits

- An upgrade of cuems-common puts the sentinel back in
  `/usr/share/cuems/cuems.service.*`. The box's own record in `/etc/avahi` is
  not touched. A tool that copies a template over it afterwards
  (`cuems-nodeconf`, which is not enabled on a box from the image) would publish
  the sentinel.
- It does not set a role, a site name, a Wi-Fi name or any password.
- The `/etc/hosts` line `127.0.0.1 controller.local # cuems-firstboot` stays
  until the box gets a role. It wins over mDNS: a box made a node by hand has to
  take it out. `cuems-set-role` does (`set-role.md`).
- The state file is what lets a failed first boot go on. Without it, a box that
  already got its uuid is refused and goes on to its normal boot half born.
