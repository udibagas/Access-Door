# ACCESS DOOR

## Hardware
1. Raspberry Pi
2. Micro SD
    - 16GB
    - Class 10
    - Recomendation : SanDisk
3. NFC Reader (PN532)
4. Monitor 3.5"

## Installation

Login as ```pi``` user

```
$ cd ~
$ git clone https://github.com/udibagas/Access-Door.git .
```

## Pin Assignment

PIN | Type | Assignment | Koneksi
-- | -- | -- | --
36 | OUTPUT | Trigger Buka Pintu | Relay
38 | INPUT | Status Pintu | Sensor Magnet
40 | INPUT | Buka Pintu Manual | Push Button

## Setting USB port supaya fixed

Posisi | Nama | Koneksi
-- | -- | --
Kiri atas | serial1 | Fingerprint
Kiri bawah | serial2 | NFC
Kanan atas | serial3 | -
Kanan bawah | serial4 | -

```
$ vim /etc/udev/rules.d/98-usb-serial.rules
```

Isi file sbb:

```
ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", KERNELS=="1-1.2", SYMLINK+="serial1"
ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", KERNELS=="1-1.3", SYMLINK+="serial2"
ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", KERNELS=="1-1.4", SYMLINK+="serial3"
ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", KERNELS=="1-1.5", SYMLINK+="serial4"
```

## Agar running otomastis setelah boot

```
$ cd ~
$ vim .confg/lxsession/LXDEPi/autostart
```

tambahkan baris berikut

```
@python access_door.py run 2> error.log
```

## Menjalankan program

Jika lewat SSH ketik perintah berikut:

```
$ export DISPLAY=:0
```

Kemudian:

```
$ python access_door.py run &
```

## CLI (Enroll, List, Hapus, Log, dsb)

Pastikan program access door mati dengan perintah berikut:

```
$ killall python
```

```
$ python access_door.py
```

Ketik ```?``` untuk melihat perintah yang tersedia

Untuk menjalanan program utama ketik perintah:

```
access_door> run
```
