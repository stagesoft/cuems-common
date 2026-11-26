<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
-->

# Platform profiles

One system image serves several kinds of box. Everything that differs between
them is a **profile**: `/usr/share/cuems/platform/<id>/platform.conf`.
`cuems-platform` reads it.

```
cuems-platform detect             # the platform id, or "unknown" (exit 3)
sudo cuems-platform apply         # write this platform's settings
cuems-platform apply --dry-run    # say what would change; writes nothing
cuems-platform check              # PASS / FAIL / MANUAL, one line per item
```

`apply` is run by the first boot or by an operator. **No package script runs
it**, so installing or upgrading cuems-common changes no kernel line, port name
or sound card on a box.

## What `apply` does

| File | Content |
|---|---|
| `/etc/default/grub.d/cuems-platform.cfg` | the profile's kernel parameters (none on N97, N100 and FP530) |
| `/etc/systemd/network/10-{ethernet0,ethernet1,wifi0}.link` | the port names, from the rule below. These replace the package's N97 files and stay conffiles: on an upgrade, **keep your version** |
| `/etc/modprobe.d/cuems-platform.conf` | ALSA card numbers (where USB audio goes) |
| `/etc/udev/rules.d/70-cuems-analog-card.rules` | the ALSA id `Analog` for the internal analog card |
| `/etc/cuems/gpu-pin.conf` | `enabled=` (and `level=high` when on) |

It then runs `update-initramfs -u` and `update-grub` where needed. If one fails,
the next `apply` runs it again. Nothing changes until the **next reboot**. A
second `apply` changes nothing.

It writes nothing when the platform is unknown (exit 3), when the ports do not
fit the rule (exit 4), when a project is loaded (exit 6,
`/tmp/cuems.show.lock`) or when `/etc/default/jack` opens the analog card by
the id it is about to lose (exit 7: change it to `hw:Analog,N` first; `apply`
never writes that file). Exit 5 means a rebuild failed: run it again before
rebooting. With no analog card to be found it warns and applies the rest.

## Before running it on a box that is already in use

`apply` is made for a box coming from the base image. On an installed box:

- **Ports can move.** The rule for the N97 names the higher-addressed wired port
  `ethernet0`; the `.link` files that cuems-common ships name the lower one. On
  an N97 still using those files, `apply` swaps `ethernet0` and `ethernet1`, so
  the cables have to follow. It warns when a name in use would move. The old
  `.link` files are kept as `*.link.cuems-before-apply`.
- **Mixer levels.** ALSA saves them under the card id. When the analog card is
  renamed they are not restored: check the levels after the reboot.

Run `cuems-platform apply --dry-run` first and read its warnings.

## Rules instead of PCI addresses

Two units of one model can have the same devices at different PCI addresses, so
a profile does not write addresses down.

- **Ports.** Ports are counted by PCI class, so a card with no driver still
  counts. The rule needs exactly two wired PCI ports and at most one Wi-Fi card.
  `ethernet_order=ascending` names the lower-addressed wired port `ethernet0`;
  `descending` names the higher one. The Wi-Fi card is `wifi0`. With no Wi-Fi
  card, the `wifi0` file matches nothing. USB network adapters are not counted.
- **Analog card.** It is the one PCI sound card with the codec named in
  `analog_codec`. It gets the id `Analog`, so that one `/etc/default/jack`
  (`-dhw:Analog,0`) serves every platform.

## Fields of `platform.conf`

`key=value`, `#` for comments. An unknown key is an error.

| Key | Meaning |
|---|---|
| `cpu_model` (required) | regular expression, matched against `model name` of `/proc/cpuinfo` |
| `gpu_pci_id` | `vendor:device`; when given it must be present too. DMI is not used: some boards report a generic name |
| `accepted` (required) | `true` only once a box of this platform has passed the image tests. `check` says when it is `false` |
| `kernel_params` | words added to the kernel command line |
| `ethernet_order` | `ascending` or `descending`; empty means the ports have not been read, and `apply` refuses |
| `analog_codec` | codec name of the internal analog card; empty means unknown (`check` says MANUAL) |
| `hda_index`, `usb_audio_index` | `index=` for `snd_hda_intel` and `snd_usb_audio` |
| `gpu_pin` | `true` or `false` |
| `firmware` | packages that must be installed |
| `aperture_mb`, `vram_mb`, `secure_boot=off`, `tpm=present` | BIOS settings Linux can see |
| `manual` (repeatable) | BIOS settings it cannot see; `check` lists them |

## What `check` compares

The platform, whether the profile is accepted, the kernel command line (a
missing parameter **or one this platform's profile does not declare** fails),
`options` lines in `/etc/modprobe.d/` (the same), the `.link` files and the live
port names, the analog card's id, the card that `/etc/default/jack` opens, the
GPU pin, the firmware packages and the BIOS items.
It exits 1 if any line says FAIL.

## The platforms

Read on one box of each model on 2026-11-26. A reading is not an acceptance:
every profile says `accepted=false` until the image tests pass on it.

| | N97 | FP530 |
|---|---|---|
| CPU | Intel N97 | AMD Ryzen Embedded R2314 |
| GPU | `8086:46d1` | `1002:15d8` |
| Wired ports on that box; `ethernet0` | `01:00.0`, `02:00.0`; the higher | `01:00.0`, `02:00.0`; the lower (other units have them at `02:00.0`, `03:00.0`) |
| Wi-Fi on that box | `03:00.0` | `03:00.0` (other units: `04:00.0`) |
| Analog card on that box | ALC897 on `00:1f.3`, id `PCH` (it carries HDMI too) | ALC897 on `04:00.6`, id `Generic_1`. The id and the address both differ between units |
| USB audio index | 1 | 2 (two HDA controllers take 0 and 1) |
| GPU pin | off | on |
| Video connectors | 3 | 4 |

**N100:** compatibility only; the base image is not built for it and does not
have to pass on it. No box has been read. Its profile has no port rule and no
analog codec, so `apply` refuses it. **i3-1215U** and **Core Ultra 5 125U** are data
only, for boxes bought for trials.

N97 and FP530 also carry a starting `default_mappings.xml` beside the profile:
every video output and the internal analog output. The first boot installs it
only where a box has none (`first-boot.md`); `apply` never writes it.

## Adding a platform

Add a directory with a `platform.conf`, fill in only what was read on a real
box, leave `accepted=false`, and run `tests/test_platform.py`. Then run
`cuems-platform apply --dry-run` and `check` on a box of that model.
