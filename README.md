# cuems-common

System-wide configuration, systemd unit files, role-aware helpers and
shared data shipped to every CUEMS node. Built as a single Debian
package consumed by both controller and node hosts.

## Operator quick reference

- **Default credentials (operator user, WiFi PSK, org SSH key):**
  [`docs/default-credentials.md`](docs/default-credentials.md) — these
  ship as known defaults on every fresh node and **must be rotated
  during deployment hardening**.
- **WiFi-AP firewall fence (opt-in nftables):**
  `/usr/share/doc/cuems-common/firewall.README` on an installed host,
  or [`usr/share/doc/cuems-common/firewall.README`](usr/share/doc/cuems-common/firewall.README)
  in this repo.
- **Node identity model:**
  [`docs/node-identity-contract.md`](docs/node-identity-contract.md).
- **OLA install procedure:**
  [`docs/ola-install.md`](docs/ola-install.md).
- **Latency tuning:**
  [`docs/latency-tuning.md`](docs/latency-tuning.md).

## Building

```sh
debuild -b -uc -us -nc
```
