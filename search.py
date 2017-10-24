#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pyfingerprint.pyfingerprint import PyFingerprint
#import RPi.GPIO as GPIO
from datetime import datetime
import time


def secs(start_time):
    dt = datetime.now() - start_time
    return dt.seconds

try:
    f = PyFingerprint('/dev/ttyUSB0', 57600, 0xFFFFFFFF, 0x00000000)

    if not f.verifyPassword():
        raise ValueError('Password fingerprint salah!')

except Exception as e:
    print('Gagal menginisialisasi fingerprint!')
    print('Pesan kesalahan: ' + str(e))
    exit(1)

## Informasi fingerprint
print('Template terpakai saat ini: ' + str(f.getTemplateCount()) + '/' + str(f.getStorageCapacity()))

## Scan jari
try:
    # Looping terus menerus
    while True:
        print('Tempelkan jari...')

        while not f.readImage():
            pass

        f.convertImage(0x01)
        result = f.searchTemplate()

        positionNumber = result[0]

        if positionNumber == -1:
            print('Sidik jari tidak ditemukan!')
            exit(0)

        else:
            print('Selamat datang. Silakan masuk.')

            # PIN pada raspberry
            pintu_terbuka = 36  # indikator bahwa pintu terbuka
            buka_pintu = 38  # untuk trigger buka pintu

            # inisiasi GPIO pada raspberry
            #GPIO.setmode(GPIO.BOARD)
            #GPIO.setwarnings(False)
            #GPIO.setup(buka_pintu, GPIO.OUT)
            #GPIO.setup(pintu_terbuka, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # buka kunci pintu
            #GPIO.output(buka_pintu, 1)

            # informasi untuk menutup pintu jika pintu masih terbuka
            #while GPIO.input(pintu_terbuka) == 1:
                #print("MOHON TUTUP PINTU")
                #time.sleep(3)

            # kunci kembali pintu
            #GPIO.output(buka_pintu, 0)

except Exception as e:
    print('Operasi gagal!')
    print('Pesan kesalahan: ' + str(e))
    GPIO.cleanup()
    exit(1)
