#!/bin/bash
sleep 70
wget http://192.168.3.21/relay/0?turn=on
sleep 10
wget http://192.168.3.20/relay/0?turn=on
sleep 10
wakeonlan -i 192.168.2.255 00:e0:4c:03:12:12
wakeonlan -i 192.168.2.255 00:e0:4c:03:11:9a
wakeonlan -i 192.168.2.255 00:e0:4c:03:11:1e
wakeonlan -i 192.168.4.255 00:c0:08:90:07:f6
wakeonlan -i 192.168.2.255 00:e0:4c:02:06:a5
sleep  70
/usr/bin/python3.7 /home/stagelab/src/cuems-wsclient/wsclient.py
sleep 10
sudo /usr/local/bin/jack_patchs.sh
exit 0
