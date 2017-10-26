#!/bin/bash

purwakarta=(
    'pi@10.45.5.126'
    'pi@10.45.5.127'
    'pi@10.45.5.128'
)

kementan=(
    'pi@192.168.99.201'
    'pi@192.168.99.202'
    'pi@192.168.99.203'
    'pi@192.168.99.204'
    'pi@192.168.99.205'
    'pi@192.168.99.206'
    'pi@192.168.99.207'
    'pi@192.168.99.208'
)

tes=('pi@10.42.0.117')

# echo $1
# server=$1
# echo server

# ssh -t pi@10.42.0.117 'bash -s' < pull.sh
for i in ${$1[@]}; do
ssh -t $i <<-'ENDSSH'
    cd ACCESS_DOOR
    git pull
    killall python
    export DISPLAY=:0
    python access_door.py run &
ENDSSH
done
