#!/bin/bash
wget http://192.168.3.20/relay/0?turn=off
ssh stagelab@192.168.2.200 sudo shutdown -h now
ssh stagelab@192.168.2.201 sudo shutdown -h now
ssh stagelab@192.168.2.202 sudo shutdown -h now
ssh stagelab@192.168.2.203 sudo shutdown -h now
ssh stagelab@192.168.4.211 sudo shutdown -h now
wget http://192.168.3.21/relay/0?turn=off
