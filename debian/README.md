# CUEMS Common Debian Package

This directory contains the Debian packaging files for CUEMS Common.

## Files

- **`install`** - Maps source files to installation destinations
- **`rules`** - Makefile that ensures scripts are executable during packaging
- **`postinst`** - Post-installation script that verifies permissions and sets up the system

## Building the Package

1. Ensure scripts are executable:
   ```bash
   ./scripts/ensure-executable.sh
   ```

2. Build the package:
   ```bash
   dpkg-buildpackage -us -uc
   ```

   Or using debuild:
   ```bash
   debuild -us -uc
   ```

## Key Features

### Automatic Executable Permissions

The `debian/rules` file automatically ensures that:
- All `.sh` files in `/usr/lib/cuems/bin/` are executable
- All `.py` files in `/usr/lib/cuems/bin/` are executable

This is done both during package building (`override_dh_install`) and after installation (`override_dh_fixperms`).

### Post-Installation Setup

The `debian/postinst` script:
1. Verifies and fixes script permissions
2. Creates Python wrapper (`/usr/lib/cuems/bin/python3`) if needed
3. Reloads systemd to pick up new unit files
4. Sets proper permissions on sensitive files (`rsyncd.secrets`, `sudoers.d/99-cuems`)

## Verification

After building and installing the package, verify:

```bash
# Check script permissions
ls -l /usr/lib/cuems/bin/

# Verify systemd units
systemd-analyze verify /etc/systemd/system/cuems-*.service

# Run package structure verification
/usr/lib/cuems/bin/verify-package-structure.sh
```

## Notes

- The `debian/install` file uses relative paths from the package root
- Scripts are automatically made executable during packaging
- The postinst script is idempotent and safe to run multiple times

