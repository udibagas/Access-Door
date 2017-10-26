#!/bin/bash

cd ACCESS_DOOR
git pull
killall python
export DISPLAY=:0
python access_door.py run &
