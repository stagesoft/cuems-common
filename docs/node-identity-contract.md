<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Ion Reguera <ion@stagelab.coop>
-->

# CUEMS Node Identity Contract

This document is the authoritative specification of how CUEMS identifies
nodes across the cluster. It is consumed by:

- `cuems-nodeconf` (writes identity to `/etc/cuems/network_map.xml` and
  the OS hostname).
- `cuems-logs` (resolves operator-friendly node names to journalctl
  `_HOSTNAME` filters).
- `cuems-editor` (propagates identity fields to the WebSocket payload).
- `cuems-frontend` (displays the operator-friendly label).

The schema is enforced by `etc/cuems/network_map.xsd` (shipped in this
repository).

## Identity model

Every adopted node has these fields in `network_map.xml`:

| Field        | Required | Stable | Source         | Purpose                                           |
|--------------|----------|--------|----------------|---------------------------------------------------|
| `uuid`       | yes      | YES    | provisioning   | primary key, never changes during hardware life   |
| `mac`        | yes      | YES    | hardware       | informational, matches one NIC                    |
| `name`       | yes      | YES    | nodeconf       | mDNS FQDN (`<mac>._cuems_nodeconf._tcp.local.`)  |
| `node_role`  | yes      | NO     | operator       | `controller`, `node`, or `firstrun` (feature 007 — was `node_type`, `NodeType.master`/`NodeType.slave`) |
| `ip`         | yes      | NO     | nodeconf       | link-local IP discovered via avahi                |
| `adopted`    | opt      | NO     | nodeconf       | `True` once adopted                               |
| `online`     | opt      | NO     | nodeconf       | last-known liveness                               |
| `role_id`    | opt      | NO*    | nodeconf       | `controller` or `nodeNN` — see assignment rules   |
| `alias`      | opt      | NO     | operator (UI)  | free-form human label                             |
| `hostname`   | opt      | NO     | nodeconf       | TRANSITIONAL: legacy OS hostname if differs       |

`*` `role_id` changes only on a role-flip (controller↔node), which is a
planned, reboot-mandatory procedure (see "Role-flip" below).

**UUID is the primary key.** Every consumer (engine, editor, nodeconf,
cuems-logs) identifies nodes by UUID. role_id/alias/hostname/node_role
are mutable projections.

### ⚠️ Which MAC — `mac` is less stable than the table implies

On a **controller** the live `bond0` address is **not** a NIC's own: a bond
adopts the MAC of its **first slave** and forces it onto the others. Until
`1.3.0-20` `interfaces.master` listed `wifi0` first, so controllers presented
the **WiFi card's** MAC on the ethernet wire — and any `mac` recorded from
`ip link show bond0` captured that, not a permanent hardware address.

The fleet noticed this independently before it was understood. In
`cuems-fleet/inventory/nodes.yaml` the **alquiler1** controller's `mac` is
annotated *"SUSPECT AS A PK … very likely bond0's adopted MAC and NOT
ethernet0's permanent hwaddr"*, and **sala1** carries the same mismatch.

**The rule:** record `ethernet0`'s **permanent** address — read it from
`/proc/net/bonding/bond0` (`Permanent HW addr` per slave) or `ethtool -P
ethernet0`, **never** from `/sys/class/net/*/address`, which shows the
bond-imposed value on every slave. The same address is what a DHCP reservation
must be keyed to, and what WoL must target (`cuems-fleet` records that WoL goes
to the **ethernet** MACs — a bond/bridge address is useless for it).

Three states coexist in the fleet as of 2026-08-31, deliberately:

| state | hosts | how |
|---|---|---|
| unfixed | most deployed controllers | bond adopts `wifi0`'s MAC; left as-is on purpose |
| **pinned** | alquiler1, sala1 | `hwaddress ether <ethernet0 mac>` in the `bond0` stanza — deployed 2026-08-28, *"VERIFIED across 2 reboots, lease + node identity preserved"* |
| **reordered** | test2, and every controller built from `1.3.0-20` onward | `bond-slaves ethernet0 wifi0` — needs no per-host value, so it fits the shipped template |

An operator finding an explicit `hwaddress ether` line on a venue box is looking
at the second state. It is correct and was proven; it is simply not what a
template can carry.

## The `node_type` -> `node_role` migration (feature 007)

`network_map.xml` documents written before this change carry `<node_type>`
(free text: `NodeType.master`, `NodeType.slave`, `NodeType.firstrun`, or the
bare `master`/`slave`/`firstrun` spelling). `cuems-migrate-network-map`
(`/usr/bin/cuems-migrate-network-map`) converts a document in place, run
automatically from `debian/postinst` on every package install/upgrade —
an operator does not need to run it by hand.

**Recovery, if a conversion needs to be undone.** No reverse conversion is
provided or planned — `node_role`'s enumeration is a narrower vocabulary
than free text was, and there is no principled string a converted value
reverts to (`controller` could have come from `NodeType.master` or the
bare `master`; the mapping is not invertible). The only path back is the
timestamped backup the conversion writes **before any change**, beside the
original file:

```bash
ls -la /etc/cuems/network_map.xml.*.bak   # newest is the most recent conversion
sudo cp /etc/cuems/network_map.xml.20260824T120000Z.bak /etc/cuems/network_map.xml
```

Restoring reproduces the pre-conversion bytes exactly — the backup is a
plain copy of the file as it stood immediately before the rewrite, taken
unconditionally, every time the script actually converts something (not on
a no-op run, so repeated idempotent installs do not accumulate backups
without bound — the five most recent are kept, older ones pruned).

A document that still carries an **unrecognised** `<node_type>` value (not
one of the six accepted spellings above) is refused whole by the
conversion — nothing is written, the file is left exactly as it was, and
`postinst` still exits 0 (the upgrade is never blocked by a bad map). Edit
the offending `<node_type>` value by hand to one of the accepted spellings
and reinstall (or re-run `/usr/bin/cuems-migrate-network-map
/etc/cuems/network_map.xml` directly) to retry.

## Role-id assignment rules (cuems-nodeconf)

### New adoption (node has no entry in network_map.xml)

When `cuems-nodeconf` adopts a node whose UUID is not in
`network_map.xml`:

1. Acquire `/var/lock/cuems-nodeconf-adopt.lock` (serializes concurrent
   adoptions; without the lock, two nodes adopted in parallel could
   both compute `node01`).

2. Compute `role_id` based on `<node_role>`:
   - `controller`:
     - If `<role_id>controller</role_id>` is already assigned to a
       different UUID → abort with error: "controller already assigned
       to UUID <other>; demote that node first before promoting this
       one".
     - Otherwise → `role_id = "controller"`.
   - `node`:
     - Read all existing `<role_id>` values matching `^node(\d+)$`,
       compute `next_n = max(existing or [0]) + 1`, assign
       `f"node{next_n:02d}"` (minimum two-digit padding, no upper
       bound — `node100` is valid).
   - If multiple nodes in the XML declare `<node_role>controller</node_role>` → emit
     a `WARNING` to stderr (do not abort) so the operator notices the
     inconsistency.

3. Read `/etc/cuems/cluster.conf` (safe parser, never `source`/`eval`)
   to compose final OS hostname:
   - If `cluster_name` present and != `default`:
     `final_hostname = f"{cluster_name}-{role_id}".lower()`.
   - Otherwise: `final_hostname = role_id.lower()`.

4. Emit a structured journal event **before** applying the SO change
   (so the event lands under the old `_HOSTNAME` for historical
   traceability):

   ```python
   from systemd import journal
   journal.send(
       f"role_id changed for node {local_uuid}: "
       f"{old_role_id or '<none>'} -> {role_id}",
       SYSLOG_IDENTIFIER="cuems-nodeconf",
       CUEMS_NODE_UUID=local_uuid,
       CUEMS_OLD_ROLE_ID=old_role_id or "",
       CUEMS_NEW_ROLE_ID=role_id,
       CUEMS_OLD_HOSTNAME=old_hostname or "",
       CUEMS_NEW_HOSTNAME=final_hostname,
       PRIORITY=5,
   )
   ```

5. Apply to the SO (idempotent):
   - `hostnamectl set-hostname <final_hostname>`.
   - `rewrite_hosts_line("127.0.1.1", final_hostname)` — see helper
     below.
   - `rewrite_avahi_host_name(final_hostname)` — see helper below.
   - **Only during automatic adoption**, restart services that cache
     the hostname:
     `avahi-daemon`, `rtpmidid`, `systemd-journal-upload`.
     During `apply-identity` (manual role-flip), DO NOT restart;
     the mandatory reboot picks them up cleanly.

6. Persist to XML:
   - `<role_id>` with the assigned value.
   - `<alias>` empty (operator sets it via the UI when needed).
   - `<hostname>` ABSENT for new-style nodes (OS hostname == role_id).

### Legacy adoption (existing node with numeric OS hostname, not being re-provisioned)

When `cuems-nodeconf` is reactivated on a node whose OS hostname does
NOT match `^(<cluster>-)?(controller|node\d+)$`:

1. Same `role_id` computation as above.
2. `<hostname>` IS persisted with `socket.gethostname()` — bridges
   operator-friendly `role_id` to the actual OS `_HOSTNAME` in the
   journal during the transition.
3. `hostnamectl set-hostname` is NOT executed. The operator chose to
   keep numeric hostnames until re-provisioning.

### Re-adoption (UUID already in XML)

- Same `node_role` → reuse existing `role_id`.
- Different `node_role` (role-flip) → follow "Role-flip" below.

## Role-flip (planned, reboot mandatory)

Role-flips MUST NEVER occur mid-show. The procedure:

```bash
# 1. Cluster outside show, no project loaded. Verify with the UI or:
cuems-logs -c engine -e --since "5 min ago"

# 2. Edit /etc/cuems/network_map.xml — change <node_role> on affected
#    nodes (node <-> controller).

# 3. Validate the XML against the schema.
xmllint --noout --schema /etc/cuems/network_map.xsd /etc/cuems/network_map.xml

# 4. Pre-check (dry-run): the operator sees what apply-identity would
#    do, without touching anything.
sudo cuems-nodeconf apply-identity --check
# exit 0 — no drift, nothing to do
# exit 1 — drift detected, prints planned changes
# exit 2 — error (XML missing, settings.xml missing, etc.)

# 5. On EACH affected node, IN ORDER:
#    a. First on nodes that demote (controller -> node) — they release
#       the "controller" role_id.
#    b. Then on nodes that promote (node -> controller) — they claim
#       "controller".
#    Skipping order risks "controller already assigned to UUID <other>"
#    aborts. apply-identity refuses to assign a duplicate "controller".
sudo cuems-nodeconf apply-identity

# 6. Reboot the affected nodes.
sudo reboot

# 7. After boot:
hostname                        # reflects the new role_id
avahi-resolve -n controller.local  # only on the new controller
cuems-logs --list-nodes         # coherent table
journalctl CUEMS_NODE_UUID=<uuid> -n 20  # includes the role_id change
```

### `apply-identity` subcommand semantics

`cuems-nodeconf apply-identity`:
- Reads local UUID from `/etc/cuems/settings.xml` (`.//node/uuid`).
  Aborts if missing ("this node has no CUEMS identity provisioned").
- Looks up the local node in `network_map.xml` by UUID.
- Re-computes `role_id` per the rules above.
- If `(old_role_id, old_hostname) == (new_role_id, new_final_hostname)`
  → prints "no changes detected (already in sync)" and returns 0
  WITHOUT emitting a duplicate journal event (idempotent).
- Otherwise: emits the structured journal event, applies the SO chain
  (`hostnamectl` + `/etc/hosts` + avahi-daemon.conf), updates
  `<role_id>` in the XML, prints "Identity applied. Reboot to
  activate.".
- Does NOT restart services; the mandatory reboot picks them up.

`cuems-nodeconf apply-identity --check`:
- Same lookup, no writes.
- Prints planned changes to stdout (hostname old → new, role_id old
  → new).
- Exit 0 if no drift; 1 if drift pending; 2 on error.

### Implementation notes

- The CLI must be invocable standalone (not require the systemd
  service running). Recommended `pyproject.toml`:

  ```toml
  [project.scripts]
  cuems-nodeconf = "cuems_nodeconf.cli:main"
  ```

  with `main()` dispatching `adopt`, `apply-identity`,
  `apply-identity --check`.

- Add `python3-systemd` to the .deb `Depends:` (used by
  `journal.send()`). Verified present on existing deployments.

- Safe parser for `/etc/cuems/cluster.conf` (never `source`/`eval`):

  ```python
  import configparser
  from pathlib import Path
  parser = configparser.ConfigParser(default_section="DEFAULT")
  parser.read_string("[DEFAULT]\n" + Path("/etc/cuems/cluster.conf").read_text())
  cluster_name = parser["DEFAULT"].get("cluster_name", "default").strip()
  ```

## SO-side helper specifications

### `rewrite_hosts_line(prefix, hostname)`

`/etc/hosts` modifications must update or insert the `127.0.1.1` line:

```python
def rewrite_hosts_line(prefix, hostname):
    path = Path("/etc/hosts")
    lines = path.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith(prefix + "\t") or line.startswith(prefix + " "):
            lines[i] = f"{prefix}\t{hostname}"
            found = True
            break
    if not found:
        lines.insert(1, f"{prefix}\t{hostname}")
    path.write_text("\n".join(lines) + "\n")
```

### `rewrite_avahi_host_name(hostname)`

`avahi-daemon.conf` may have the `host-name=` line commented out, active,
or absent. Prefer the active line; fall back to the commented one;
otherwise insert under `[server]`:

```python
def rewrite_avahi_host_name(hostname):
    path = Path("/etc/avahi/avahi-daemon.conf")
    lines = path.read_text().splitlines()
    # 1. Active (uncommented) line first.
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("#") and "host-name=" in line.replace(" ", ""):
            lines[i] = f"host-name={hostname}"
            path.write_text("\n".join(lines) + "\n")
            return
    # 2. Replace a commented entry in-place to keep surrounding context.
    for i, line in enumerate(lines):
        stripped = line.lstrip("#").strip()
        if stripped.startswith("host-name="):
            lines[i] = f"host-name={hostname}"
            path.write_text("\n".join(lines) + "\n")
            return
    # 3. Last resort: append under [server].
    for i, line in enumerate(lines):
        if line.strip() == "[server]":
            lines.insert(i + 1, f"host-name={hostname}")
            path.write_text("\n".join(lines) + "\n")
            return
    raise RuntimeError("avahi-daemon.conf has no [server] section")
```

Note: this overrides any operator-managed `host-name=` value. When
CUEMS governs identity, it governs the full chain. The avahi
collision workaround documented in the project CLAUDE.md
(setting `host-name=<MAC>` on cloned nodes) is superseded by this
mechanism — cuems-nodeconf assigns unique hostnames, eliminating
the collision class.

## Multi-cluster (reserved, not implemented)

`/etc/cuems/cluster.conf` exists to declare a cluster name. When
present, nodeconf prefixes the OS hostname with it
(`museo-planta1-controller`, `museo-planta1-node01`).

`cuems-logs` reserves the `--cluster` flag but errors out if used; the
single-cluster lookup is correct for any deployment today, even with
prefixed hostnames (the XML lookup resolves the full prefixed name via
the `<hostname>` field during the legacy transition, or via `<role_id>`
post-migration where `role_id` already includes the prefix at the OS
level).

Future work:
- Cross-cluster journal federation.
- `cuems-logs --cluster <name>` to filter by cluster.
- UI awareness of multi-cluster topology.

## During the transition (operator workflow with nodeconf disabled)

While `cuems-nodeconf` is disabled cluster-wide, the operator manages
the new identity fields by hand to enable `cuems-logs` semantic
filters. See the project README and the plan archived at
`.claude/plans/mejorar-comando-cuems-log-a-adir-happy-engelbart.md`
for the runbook.

Minimal flow:

```bash
sudo cp /etc/cuems/network_map.xml /etc/cuems/network_map.xml.bak

# Edit each <node>, appending the three fields before </node>:
#   <role_id>controller</role_id>   (the controller)
#   <role_id>node01</role_id>       (first node)
#   <hostname>000000000002</hostname>  (the current OS hostname, legacy)
#   <alias>controller</alias>       (optional, operator-defined)

xmllint --noout --schema /etc/cuems/network_map.xsd /etc/cuems/network_map.xml

sudo systemctl restart cuems-editor   # so it picks the new fields

cuems-logs -n controller --since today
cuems-logs --list-nodes
```
