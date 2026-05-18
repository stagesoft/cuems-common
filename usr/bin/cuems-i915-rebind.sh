#!/bin/bash
# cuems-i915-rebind.sh
# Forces a full Intel i915 GPU driver rebind before cuems-videocomposer starts.
#
# On warm restart, the i915 HDMI PHY can be left in a miscalibrated state due
# to a VBT (Video BIOS Table) parsing bug in kernel 6.1 for Alder Lake-N
# (VBT version 256 child device config size mismatch). This rebind forces the
# driver to re-run its full PHY initialisation sequence from a clean state,
# equivalent to what a cold boot does.
#
# Must run as root (ExecStartPre=+ in the service unit).

PCI="0000:00:02.0"
DRIVER="/sys/bus/pci/drivers/i915"

if [ ! -L "$DRIVER/$PCI" ]; then
    echo "cuems-i915-rebind: i915 not bound at $PCI, skipping"
    exit 0
fi

echo "cuems-i915-rebind: unbinding i915 to force HDMI PHY reset..."
plymouth quit 2>/dev/null || true
sleep 0.3
echo "$PCI" > "$DRIVER/unbind"
sleep 0.5
echo "cuems-i915-rebind: rebinding i915..."
echo "$PCI" > "$DRIVER/bind"
sleep 1
echo "cuems-i915-rebind: done"
