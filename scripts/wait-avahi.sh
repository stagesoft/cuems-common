#!/bin/bash
MAC=$(grep -Po '(?<=<mac>)(\w+)(?=..<\/mac>)' /etc/cuems/settings.xml)

while ! avahi-browse -apt |grep _cuems_nodeconf |grep $MAC >/dev/null
do
	echo "Waiting for avahi to publish own service.."
	sleep 2
done
echo "Avahi service present!, executing nodeconf now"
