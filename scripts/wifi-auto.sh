#/bin/bash
systemctl stop isc-dhcp-server && ifdown wlo2 && ifup wlo2=wifi-out
