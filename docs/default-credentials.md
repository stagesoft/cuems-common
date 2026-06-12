# CUEMS default credentials

Every freshly-imaged CUEMS node ships with a known, published credential
surface so a technician can reach the box on first boot. Operators are
expected to rotate these during deployment hardening (procedure at the
bottom of this document). The defaults below are the same on every node
running `cuems-common` from this version of the package.

## Operator account

| Field    | Value                  |
|----------|------------------------|
| Username | `cuems-admin`          |
| Password | `cuems-admin-default`  |
| Sudo     | full (`ALL=(ALL) ALL`) |

Use this account at the physical TTY console or over SSH. `sudo -i` from
this account is the escalation path for tasks needing root.

## Root account

**Locked by design.** Direct root login is disabled (`PermitRootLogin no`
in sshd, `passwd -l root` at install). The cuems-admin account with sudo
is the only path to root.

To recover from a sudo lockout:

1. Boot to GRUB recovery mode (physical access required), or
2. Boot with `init=/bin/bash` and `passwd -u root` from the resulting
   shell.

## SSH

- Pubkey-only — `PasswordAuthentication no` (over SSH; console TTY still
  accepts passwords).
- The Stagelab organization public key is shipped at
  `/etc/cuems/ssh/cuems-org.pub` and planted in `cuems-admin`'s
  `~/.ssh/authorized_keys` on first install.
- The matching **private key** is held by Stagelab Coop. Engineers
  connect with `ssh -i ~/.ssh/cuems-org cuems-admin@<host>`.

To add per-engineer keys on a node (additive — won't kick the org key):

```sh
ssh cuems-admin@<host> "tee -a ~/.ssh/authorized_keys" < my-laptop-key.pub
```

To revoke the org key from a specific node (e.g. customer-managed
deployment):

```sh
ssh cuems-admin@<host> 'sed -i "/cuems-org@stagelab.coop/d" ~/.ssh/authorized_keys'
```

## WiFi (controllers only)

The `cuems-controller.target` pulls `hostapd.service`, broadcasting an
AP on `wifi0` for operator laptop access. Nodes (running only
`cuems-node.target`) do not have an AP.

| Field      | Value                                                                     |
|------------|---------------------------------------------------------------------------|
| SSID       | `cuems` (or `cuems-<cluster_name>` if `/etc/cuems/cluster.conf` is set)   |
| WPA2 PSK   | `cuems-wifi-default`                                                      |
| Channel    | 2.4 GHz, channel 1                                                        |

The runtime hostapd config is rendered from
`/usr/share/cuems/hostapd/hostapd.conf.template` into
`/run/cuems/hostapd.conf` on every hostapd start, by
`/usr/lib/cuems/bin/cuems-write-hostapd-config`.

> **Note**: joining this WiFi gives layer-2 access to the cluster bus
> (NNG, OSC, rsync) by default. See
> `/usr/share/doc/cuems-common/firewall.README` for the opt-in nftables
> fence that restricts AP guests to the operator surface (SSH, UI, DHCP,
> mDNS).

## Hardening for production deployment

These defaults are convenient for first-boot but unacceptable past
deployment. Recommended hardening pass per node:

1. **Rotate the operator password.**
   ```sh
   sudo passwd cuems-admin
   ```

2. **Add per-engineer / per-customer SSH keys, then drop the org key.**
   ```sh
   # Add the customer's key first (don't lock yourself out)
   echo "<customer pubkey>" >> ~/.ssh/authorized_keys
   # Verify the customer can SSH in with their key
   # ... then drop the org key
   sed -i '/cuems-org@stagelab.coop/d' ~/.ssh/authorized_keys
   ```

3. **Rotate the WiFi passphrase.**
   ```sh
   sudo sed -i 's|^wpa_passphrase=.*|wpa_passphrase=<new-passphrase>|' \
       /usr/share/cuems/hostapd/hostapd.conf.template
   sudo systemctl restart hostapd.service
   ```
   (Editing the template is the cleanest path — the helper will pick it
   up on next render.)

4. **Optionally rename the SSID per deployment.**
   Set `cluster_name=<x>` in `/etc/cuems/cluster.conf` so the SSID
   becomes `cuems-<x>`, then restart `hostapd.service`.

5. **Enable the WiFi-fence nftables ruleset** (see
   `/usr/share/doc/cuems-common/firewall.README`).

6. **Verify the result.**
   ```sh
   # SSH must refuse password auth
   ssh -o PreferredAuthentications=password cuems-admin@<host>
   # Root SSH must be refused
   ssh root@<host>
   # cuems-admin can sudo
   ssh -i <new-key> cuems-admin@<host> 'sudo -n true && echo OK'
   ```

## Where these defaults live in code

| Default                      | Single source of truth                                              |
|------------------------------|---------------------------------------------------------------------|
| Operator password            | `DEFAULT_OPERATOR_PASSWORD` in `debian/postinst`                    |
| WiFi WPA2 passphrase         | `DEFAULT_PASSPHRASE` in `/usr/lib/cuems/bin/cuems-write-hostapd-config` |
| Org public key               | `/etc/cuems/ssh/cuems-org.pub` (private half: Stagelab password manager) |
| sshd hardening               | `/etc/ssh/sshd_config.d/50-cuems.conf`                              |
| Operator sudo                | `/etc/sudoers.d/50-cuems-admin`                                     |
