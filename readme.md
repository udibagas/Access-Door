# ACCESS DOOR

## Hardware
1. Raspberry Pi
2. Micro SD
    - 16GB
    - Class 10
    - Recomendation : SanDisk
3. NFC Reader (PN532)
4. Sensor magnet (untuk status pintu tertutup/terbuka)
5. Push button (untuk membuka pintu manual dari receptionist)
6. Monitor 3.5"
7. USB to Serial adapter
8. USB Keyboard
9. USB Mouse
10. HDMI Monitor


## Instalasi OS
1. Download OS untuk raspberry pi (raspbian) di link berikut: http://vx2-downloads.raspberrypi.org/raspbian/images/raspbian-2017-08-17/2017-08-16-raspbian-stretch.zip

2. Ikuti langkah pada link berikut untuk instalasi OS pada SD card: https://www.raspberrypi.org/documentation/installation/installing-images/README.md

## Setting raspbian
1. Koneksikan raspberry pi ke keyboard, mouse dan monitor
2. Buka terminal, check link below: https://www.raspberrypi.org/documentation/configuration/raspi-config.md

    Parameter yang perlu di setting:
    - Interface yg harus dienablekan = SPI, SSH, Serial
    - Booting GUI with user pi
    - Timezone
    - Locale
    - Overclock to turbo (if available)

3. Setting IP address untuk keperluan remote (SSH)


## Package Dependency

```
sudo apt install python-pysqlite2 python-texttable python-qt4
```

Install pyfingerprint. Refer to below link.

https://github.com/bastianraschke/pyfingerprint

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
$ sudo vim /etc/udev/rules.d/98-usb-serial.rules
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
$ vim ~/.config/lxsession/LXDE-pi/autostart
```

tambahkan baris berikut

```
@python access_door.py run 2> error.log
```

tambahkan baris berikut agar layar tidak blank

```
@xset s off
@xset -dpms
@xset s noblank
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
