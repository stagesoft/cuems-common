#!/bin/bash
static_ip="192.168.6.1"
ip=$(ip -4 addr show bond0 |grep -oP "(?<=inet ).*(?=/)")
ethernet0_connected=$(ethtool ethernet0 | grep -oP "(?<=Link detected: )(.*)")
if [[ -n "$ip" ]]; then
	if [[ "$ip" == "$static_ip" ]]; then
		if [[ "$ethernet0_connected" == "no" ]]; then
			exit 0
		else
			exit 1
		fi
	else
		exit 1
	fi
else
	exit 255
fi
