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
    - Expand file system
    - Interface yg harus dienablekan = SPI, SSH, Serial
    - Booting GUI with user pi
    - Timezone
    - Locale
    - Overclock to turbo (if available)

3. Setting IP address untuk keperluan remote (SSH)

## Setting Monitor 3.5"

Pasang monitor pada raspberry pi.

```
$ sudo apt update && sudo apt upgrade
$ sudo rpi-update
$ sudo vim /usr/share/X11/xorg.conf.d/99-fbturbo.conf
```

Ubah ```fb0``` menjadi ```fb1```

```
$ git clone https://github.com/swkim01/waveshare-dtoverlays.git
$ sudo cp waveshare-dtoverlays/waveshare35a-overlay.dtb /boot/overlays
$ sudo vim /boot/config.txt
```
Tambahkan baris berikut:

```
dtparam=spi=on
dtoverlay=waveshare35a
gpu_mem=128
```

```
$ sudo vim /etc/modules
```

Tambahkan baris berikut:

```
flexfb width=320 height=480 regwidth=16 init=-1,0xb0,0x0,-1,0x11,-2,250,-1,0x3A,0x55,-1,0xC2,0x44,-1,0xC5,0x00,0x00,0x00,0x00,-1,0xE0,0x0F,0x1F,0x1C,0x0C,0x0F,0x08,0x48,0x98,0x37,0x0A,0x13,0x04,0x11,0x0D,0x00,-1,0xE1,0x0F,0x32,0x2E,0x0B,0x0D,0x05,0x47,0x75,0x37,0x06,0x10,0x03,0x24,0x20,0x00,-1,0xE2,0x0F,0x32,0x2E,0x0B,0x0D,0x05,0x47,0x75,0x37,0x06,0x10,0x03,0x24,0x20,0x00,-1,0x36,0x28,-1,0x11,-1,0x29,-3

fbtft_device debug=3 rotate=90 name=flexfb speed=16000000 gpios=reset:25,dc:24
```

```
$ sudo vim /boot/cmdline.txt
```

Tambahkan baris berikut:

```
fbcon=map:1 fbcon=font:ProFont6x11
```

```
$ sudo reboot
```

## Package Dependency

```
$ sudo apt install python-pysqlite2 python-texttable python-qt4
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

### Raspberry Pi

PIN | Type | Assignment | Koneksi
-- | -- | -- | --
36 | OUTPUT | Trigger Buka Pintu | Relay (Pin VCC ambil dari 5V usb to serial adapter)
38 | INPUT | Status Pintu | Sensor Magnet
40 | INPUT | Buka Pintu Manual | Push Button

### Relay
PIN | Koneksi
-- | --
VCC | USB to Serial Adapter pin 5v
GND | PIN 34 Raspberry Pi
INPUT | PIN 36 Raspberry Pi
COM | PSU 12V (+)
NC | Magnetic (+)

### Fingerprint

Warna | Assignment | USB to Serial Adapter Pin
-- | -- | --
Merah | VCC 3.3V | VCC 3.3V
Putih | RX | TX
Hijau | TX | RX
Hitam | GND | GND

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
