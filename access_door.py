#!/usr/bin/python

from PyQt4 import QtCore, QtGui
import binascii
import PN532
import sqlite3
import time
from datetime import datetime
from pyfingerprint.pyfingerprint import PyFingerprint
from terminaltables import AsciiTable
from RPi import GPIO
import main_ui
import sys
import subprocess
import requests
import os
import json
import logging
import logging.handlers
import uuid
from threading import Thread
from pygame import mixer


class Main(QtGui.QWidget, main_ui.Ui_Form):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)
        self.info.setText("TEMPELKAN JARI ATAU KARTU ANDA")
        self.instansi.setText(config["instansi"])
        self.logo.setPixmap(QtGui.QPixmap(os.path.join(os.path.dirname(__file__), config["logo"])))

        self.update_clock()
        self.sync_user()

        self.showFullScreen()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)

        self.sync_timer = QtCore.QTimer()
        self.sync_timer.timeout.connect(self.sync_user)
        self.sync_timer.start(config["timer"]["sync"] * 1000)

        if use_fp:
            self.scan_finger_thread = ScanFingerThread()
            self.connect(self.scan_finger_thread, QtCore.SIGNAL('updateInfo'), self.update_info)
            self.connect(self.scan_finger_thread, QtCore.SIGNAL('playAudio'), self.play_audio)
            self.scan_finger_thread.start()

        if use_nfc:
            self.scan_card_thread = ScanCardThread()
            self.connect(self.scan_card_thread, QtCore.SIGNAL('updateInfo'), self.update_info)
            self.connect(self.scan_card_thread, QtCore.SIGNAL('playAudio'), self.play_audio)
            self.scan_card_thread.start()

        self.open_manual_thread = OpenManualThread()
        self.open_manual_thread.start()

    def update_info(self, info):
        self.info.setText(info)

    def update_clock(self):
        self.tanggal.setText(time.strftime("%d %b %Y"))
        self.jam.setText(time.strftime("%H:%M:%S"))

    def play_audio(self, audio_file, loops=0):
        audio = os.path.join(os.path.dirname(__file__), audio_file)
        if os.path.isfile(audio):
            try:
                mixer.music.load(audio)
            except Exception as e:
                logger.debug("Failed to play " + audio_file + " : " + str(e))
                return
            mixer.music.play(loops)

    def sync_user(self):
        try:
            r = requests.get(config["api_url"] + "pintu/staff", timeout=3)
        except Exception as e:
            logger.debug("Failed to sync user." + str(e))
            return

        if r.status_code != requests.codes.ok:
            logger.debug("Failed to sync user. " + str(r.status_code))
            return

        try:
            server_users = r.json()
        except Exception as e:
            logger.debug("Failed to sync user. " + str(e))
            return

        cur = db.cursor()
        cur.execute("SELECT `uuid`, `nama`, `jabatan`, `last_update` FROM `karyawan`")
        results = cur.fetchall()
        cur.close()

        if len(server_users) == 0 and results:
            logger.debug("Deleting all staff...")
            try:
                cur = db.cursor()
                cur.execute("DELETE FROM `karyawan`")
                cur.close()
                db.commit()
                logger.debug("All staff deleted!")

            except Exception as e:
                logger.debug("Failed to delete all staff!")
                cur.close()

            return

        local_uuids = []
        local_users = {}

        for row, item in enumerate(results):
            local_uuids.append(item[0])
            local_users[item[0]] = {
                "nama": item[1],
                "jabatan": item[2],
                "last_update": item[3]
            }

        server_uuids = []
        cur = db.cursor()

        for row, item in enumerate(server_users):
            server_uuids.append(item["uuid"])

            # edit user kalau waktu update beda
            if item["uuid"] in local_uuids:
                logger.debug("Updating " + item["nama"] + "...")
                if item["updated_at"] > local_users[item["uuid"]]["last_update"]:
                    cur.execute(
                        "UPDATE `karyawan` SET `nama` = ?, `jabatan` = ?, `last_update` = ? WHERE `uuid` = ?",
                        (item["nama"], item["jabatan"], item["updated_at"], item["uuid"])
                    )

            # tambah user kalau ada yang baru
            logger.debug("Adding " + item["nama"] + " to local database...")
            cur.execute(
                "INSERT INTO `karyawan` (`nama`, `jabatan`, `fp_id`, `card_id`, `template`, `uuid`, `last_update`) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (item["nama"], item["jabatan"], '***', item["card_id"], item["template"], item["uuid"], item["updated_at"])
            )

        cur.close()
        db.commit()

        # hapus user kalau ada yg dihapus
        deleted_uuids = []
        for i in local_uuids:
            if i not in server_uuids:
                deleted_uuids.append(i)

        if len(deleted_uuids) > 0:
            logger.debug("Deleting " + str(len(deleted_uuids)) + " user(s)...")
            cur = db.cursor()
            cur.execute(
                "DELETE FROM `karyawan` WHERE `uuid` IN (?)",
                (','.join(deleted_uuids),)
            )
            cur.close()
            db.commit()

    def buka_pintu(self, karyawan=None):
        self.play_audio('silakan_masuk.ogg')

        if karyawan:
            nama = karyawan[1].upper()
        else:
            nama = ""

        self.info.setText("SILAKAN MASUK " + nama)
        GPIO.output(config["gpio_pin"]["relay"], 1)
        timeout = False
        alarm = False
        start_time = datetime.now()

        if config["features"]["sensor_pintu"]["active"]:
            while GPIO.input(config["gpio_pin"]["sensor_pintu"]) == config["features"]["sensor_pintu"]["default_state"]:
                time.sleep(0.2)
                if secs(start_time) > config["timer"]["timeout"]:
                    timeout = True
                    break

        if timeout:
            GPIO.output(config["gpio_pin"]["relay"], 0)
            self.info.setText("WAKTU HABIS")
            self.play_audio("waktu_habis.ogg")
            time.sleep(3)
            self.info.setText("TEMPELKAN JARI ATAU KARTU ANDA")
            return

        if karyawan:
            cur = db.cursor()
            cur.execute("INSERT INTO `log` (`karyawan_id`) VALUES (?)", (karyawan[0],))
            cur.close()
            db.commit()

        if nama == "":
            nama = "MANUAL"

        data = {'access_by': nama, 'status': 0}

        try:
            r = requests.post(config["api_url"] + "logPintu", data=data, timeout=3)
        except Exception as e:
            logger.debug("GAGAL mengirim log ke server")

        if r.status_code == requests.codes.ok:
            logger.debug("SUKSES mengirim log ke server")
        else:
            logger.debug("GAGAL mengirim log ke server")

        open_time = datetime.now()

        if config["features"]["sensor_pintu"]["active"]:
            while GPIO.input(config["gpio_pin"]["sensor_pintu"]) != config["features"]["sensor_pintu"]["default_state"]:
                if secs(open_time) < config["timer"]["open_duration"]:
                    time.sleep(0.2)
                    continue
                # only execute once
                if not alarm:
                    GPIO.output(config["gpio_pin"]["alarm"], 1)
                    self.info.setText("MOHON TUTUP PINTU")
                    self.play_audio('mohon_tutup_pintu.ogg')
                    time.sleep(3)
                    self.play_audio('alarm.ogg', -1)
                    alarm = True

                time.sleep(0.2)

        else:
            time.sleep(config["timer"]["open_duration"])

        # turn off alarm
        if alarm:
            GPIO.output(config["gpio_pin"]["alarm"], 0)

            try:
                mixer.music.stop()
            except Exception as e:
                pass

        # tutup pintu
        GPIO.output(config["gpio_pin"]["relay"], 0)

        # simpan log ke server (tutup)
        if nama == "":
            nama = "MANUAL"
        data = {'access_by': nama, 'status': 1}

        try:
            r = requests.post(config["api_url"] + "logPintu", data=data, timeout=3)
        except Exception as e:
            logger.debug("GAGAL mengirim log ke server")

        if r.status_code == requests.codes.ok:
            logger.debug("SUKSES mengirim log ke server")
        else:
            logger.debug("GAGAL mengirim log ke server")


class ScanCardThread(QtCore.QThread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.exiting = False

    def __del__(self):
        self.exiting = True
        self.wait()

    def run(self):
        self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ATAU KARTU ANDA")
        while not self.exiting:
            try:
                uid = pn532.read_passive_target()
            except Exception as e:
                self.emit(QtCore.SIGNAL('updateInfo'), "GAGAL MEMBACA KARTU")
                time.sleep(2)
                self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ATAU KARTU ANDA")
                continue

            if uid is "no_card":
                continue

            if GPIO.input(config["gpio_pin"]["sensor_pintu"]) != config["features"]["sensor_pintu"]["default_state"]:
                continue

            self.emit(QtCore.SIGNAL('playAudio'), "beep.ogg")
            time.sleep(0.2)
            card_id = str(binascii.hexlify(uid))

            cur = db.cursor()
            cur.execute("SELECT * FROM karyawan WHERE `card_id` = ?", (card_id,))
            result = cur.fetchone()
            cur.close()

            if result:
                ui.buka_pintu(result)
                self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ATAU KARTU ANDA")
            else:
                self.emit(QtCore.SIGNAL('updateInfo'), "KARTU TIDAK TERDAFTAR")
                self.emit(QtCore.SIGNAL('playAudio'), "kartu_tidak_terdaftar.ogg")
                time.sleep(3)
                self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ATAU KARTU ANDA")


class ScanFingerThread(QtCore.QThread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.exiting = False

    def __del__(self):
        self.exiting = True
        self.wait()

    def save_template(self, tpl):
        try:
            template = json.loads(tpl)
        except Exception as e:
            raise Exception("Template error. Invalid JSON. " + str(e))
            return False

        try:
            fp.uploadCharacteristics(0x01, template)
        except Exception as e:
            raise Exception("Failed to upload template to fingerprint reader. " + str(e))
            return False

        try:
            return fp.storeTemplate()
        except Exception as e:
            raise Exception("Failed to store template to fingerprint reader. " + str(e))
            return False

    def read_image(self):
        while not fp.readImage():
            time.sleep(config["timer"]["scan"])

    def run(self):
        while not self.exiting:
            cur = db.cursor()
            cur.execute("SELECT `id`, `template` FROM `karyawan` WHERE `fp_id` = '***' OR `fp_id` IS NULL OR `fp_id` = ''")
            results = cur.fetchall()
            cur.close()

            for row, item in enumerate(results):
                try:
                    fp_id = self.save_template(item[1])
                except Exception as e:
                    logger.error("Failed to save template." + str(e))
                    continue

                if fp_id >= 0:
                    cur = db.cursor()
                    cur.execute("UPDATE `karyawan` SET `fp_id` = ? WHERE `id` = ?", (fp_id, item[0]))
                    cur.close()
                    db.commit()

            self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ATAU KARTU ANDA")

            try:
                self.read_image()
            except Exception as e:
                logger.error("Fingerprint error. " + str(e))
                continue

            # skip when door is opened
            if GPIO.input(config["gpio_pin"]["sensor_pintu"]) != config["features"]["sensor_pintu"]["default_state"]:
                continue

            self.emit(QtCore.SIGNAL('playAudio'), "beep.ogg")

            # try:
            #     os.remove(os.path.join(os.path.dirname(__file__), "img/fp.png"))
            # except Exception as e:
            #     pass
            #
            # try:
            #     fp.downloadImage(os.path.join(os.path.dirname(__file__), "img/fp.png"))
            #     self.emit(QtCore.SIGNAL('showFpImg'))
            # except Exception as e:
            #     logger.debug("Failed to donwload image. " + str(e))

            try:
                fp.convertImage(0x01)
            except Exception as e:
                logger.debug("Failed to convert image. " + str(e))
                continue

            try:
                result = fp.searchTemplate()
            except Exception as e:
                logger.debug("Failed to search template. " + str(e))
                continue

            fp_id = result[0]

            if fp_id == -1:
                self.emit(QtCore.SIGNAL('updateInfo'), "SIDIK JARI TIDAK DITEMUKAN")
                self.emit(QtCore.SIGNAL('playAudio'), "sidik_jari_tidak_ditemukan.ogg")
                time.sleep(3)
                continue

            cur = db.cursor()
            cur.execute("SELECT `id`, `nama`, `uuid`, `last_update` FROM karyawan WHERE `fp_id` = ?", (fp_id,))
            result = cur.fetchone()
            cur.close()

            if not result:
                self.emit(QtCore.SIGNAL('updateInfo'), "HAK AKSES ANDA TELAH DICABUT")
                self.emit(QtCore.SIGNAL('playAudio'), "hak_akses_dicabut.ogg")

                try:
                    fp.deleteTemplate(fp_id)
                except Exception as e:
                    logger.debug("Template gagal dihapus." + str(e))

                time.sleep(3)
                continue

            ui.buka_pintu(result)


class OpenManualThread(QtCore.QThread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.exiting = False

    def __del__(self):
        self.exiting = True
        self.wait()

    def run(self):
        while not self.exiting:
            if GPIO.input(config["gpio_pin"]["sensor_pintu"]) == config["features"]["sensor_pintu"]["default_state"] and not GPIO.input(config["gpio_pin"]["saklar_manual"]):
                logger.debug("Open by switch")
                ui.buka_pintu()
            else:
                time.sleep(0.2)


class Console():
    def __init__(self):
        pass

    def daftar(self):
        if not use_nfc and not use_fp:
            print "NFC reader dan Fingerprint reader tidak ditemukan!"
            return

        nama = raw_input("Nama: ")
        jabatan = raw_input("Jabatan: ")
        card_id = '***'
        fp_id = '***'
        template = None
        daftar_apa = 0
        daftar_sidik_jari = 1
        daftar_kartu = 2
        daftar_semua = 3

        if not nama or not jabatan:
            print "Nama dan jabatan harus diisi. Silakan ulangi kembali"
            return

        while daftar_apa not in range(1,4):
            daftar_apa = raw_input("1 = Daftar Sidik Jari, 2 = Daftar Kartu NFC, 3 = Daftar Semua: ")
            try:
                daftar_apa = int(daftar_apa)
            except Exception as e:
                continue

        if use_fp and (daftar_apa == daftar_sidik_jari or daftar_apa == daftar_semua):
            print('Tempelkan jari Anda...')

            while not fp.readImage():
                time.sleep(config["timer"]["scan"])

            try:
                fp.convertImage(0x01)
            except Exception as e:
                print "Error convert image on buffer 0x01. " + str(e)
                return

            try:
                result = fp.searchTemplate()
            except Exception as e:
                print "Error search template. " + str(e)
                return

            positionNumber = result[0]

            if positionNumber >= 0:
                print('Jari sudah terdaftar. Silakan ulangi kembali')
                return

            print('Angkat jari...')
            time.sleep(2)

            print('Tempelkan jari yang sama...')
            while not fp.readImage():
                time.sleep(0.2)

            try:
                fp.convertImage(0x02)
            except Exception as e:
                print "Error convert image on buffer 0x02. " + str(e)
                return

            if not fp.compareCharacteristics():
                print "Sidik jari tidak sama. Silakan ulangi kembali"
                return

            try:
                fp.createTemplate()
            except Exception as e:
                print "Failed to create template. " + str(e)
                return

            try:
                fp_id = fp.storeTemplate()
            except Exception as e:
                print "Failed to store template." + str(e)
                return

            try:
                fp.loadTemplate(fp_id, 0x01)
            except Exception as e:
                print "Failed to load template." + str(e)
                return

            try:
                template = json.dumps(fp.downloadCharacteristics(0x01))
            except Exception as e:
                print "Failed to download template. Template will be generated next time."
                template = None

        if use_nfc and (daftar_apa == daftar_kartu or daftar_apa == daftar_semua):
            print "Tempelkan kartu..."

            while True:
                try:
                    uid = pn532.read_passive_target()
                except Exception as e:
                    continue
                if uid is "no_card":
                    continue

                card_id = str(binascii.hexlify(uid))
                break

            cur = db.cursor()
            cur.execute("SELECT * FROM `karyawan` WHERE card_id = ?", (card_id,))
            result = cur.fetchone()
            cur.close()

            if result:
                print "Kartu sudah terdaftar atas nama " + result[1]

                try:
                    fp.deleteTemplate(fp_id)
                except Exception as e:
                    print "Failed to delete template. " + str(e)
                    return

        if fp_id == "***" and card_id == "***":
            print "Pendaftaran GAGAL. Gagal membaca sidik jari dan kartu."
            return

        UUID = str(uuid.uuid4())

        try:
            cur = db.cursor()
            cur.execute(
                "INSERT INTO `karyawan` (`nama`, `jabatan`, `fp_id`, `card_id`, `template`, `uuid`) VALUES (?, ?, ?, ?, ?, ?)",
                (nama, jabatan, fp_id, card_id, template, UUID)
            )
            cur.close()
            db.commit()
        except Exception as e:
            print "Pendaftaran GAGAL! " + str(e)
            return

        print "Pendaftaran BERHASIL!"
        data = {
            "nama": nama,
            "jabatan": jabatan,
            "fp_id": fp_id,
            "card_id": card_id,
            "template": template,
            "uuid": UUID
        }
        print "Syncing staff data to server..."

        try:
            r = requests.post(config["api_url"] + "staff", data=data, timeout=3)
        except Exception as e:
            print "Sync staff data FAILED!" + str(e)
            return

        if r.status_code == requests.codes.ok:
            print "Sync staff data OK!"
        else:
            print "Sync staff data FAILED! " + str(r.status_code)

    def list(self):
        cur = db.cursor()
        cur.execute("SELECT `id`, `nama`, `jabatan`, `fp_id`, `card_id`, datetime(`waktu_daftar`, 'localtime') FROM `karyawan` ORDER BY `nama` ASC")
        result = cur.fetchall()
        cur.close()

        data = [["ID", "NAMA", "JABATAN", "FINGERPRINT ID", "CARD ID", "WAKTU DAFTAR"]]

        for row, item in enumerate(result):
            data.append([str(item[0]), item[1], item[2], item[3], item[4], item[5]])

        table = AsciiTable(data)
        print table.table

    def log(self):
        cur = db.cursor()
        cur.execute("SELECT datetime(`log`.`waktu`, 'localtime'), `karyawan`.`nama`, `karyawan`.`jabatan` FROM `log` LEFT JOIN `karyawan` ON `karyawan`.`id` = `log`.`karyawan_id` ORDER BY `log`.`waktu` ASC")
        result = cur.fetchall()
        cur.close()

        data = [["WAKTU MASUK", "NAMA", "JABATAN"]]

        for row, item in enumerate(result):
            data.append([str(item[0]), item[1], item[2]])

        table = AsciiTable(data)
        print table.table

    def clear_database(self):
        confirm = raw_input("Anda yakin (y/N)? ")
        if confirm != "y":
            return

        cur = db.cursor()
        cur.execute("DELETE FROM `karyawan`")
        cur.execute("DELETE FROM `log`")
        cur.close()
        db.commit()

        try:
            fp.clearDatabase()
        except Exception as e:
            print "Failed to clear database. " + str(e)

    def clear_log(self):
        confirm = raw_input("Anda yakin (y/N)? ")
        if confirm != "y":
            return

        cur = db.cursor()
        cur.execute("DELETE FROM `log`")
        cur.close()
        db.commit()

    def hapus(self):
        self.list()
        id_karyawan = raw_input("Masukkan ID yang akan Anda hapus: ")

        try:
            id_karyawan = int(id_karyawan)
        except Exception as e:
            print "ID yang Anda masukkan salah. " + str(e)
            return

        cur = db.cursor()
        cur.execute("SELECT `id`, `nama`, `jabatan`, `fp_id`, `card_id`, `waktu_daftar`, `uuid` FROM `karyawan` WHERE id = ?", (id_karyawan,))
        result = cur.fetchone()
        cur.close()

        if not result:
            print "ID karyawan tidak ditemukan."
            return

        data = [
            ["ID", "NAMA", "JABATAN", "FINGERPRINT ID", "CARD ID", "WAKTU DAFTAR"],
            [str(result[0]), result[1], result[2], result[3], result[4], result[5]]
        ]

        table = AsciiTable(data)
        print table.table

        confirm = raw_input("Anda yakin akan menghapus karyawan ini (y/n)?")
        if confirm != "y":
            return

        cur = db.cursor()
        cur.execute("DELETE FROM `karyawan` WHERE id = ?", (id_karyawan,))
        cur.close()
        db.commit()
        print "Data karyawan berhasil dihapus"

        try:
            fp.deleteTemplate(int(result[3]))
        except Exception as e:
            print "Gagal menghapus template sidik jari. " + str(e)

    def save_template(self):
        cur = db.cursor()
        cur.execute("SELECT * FROM `karyawan` WHERE `template` IS NULL")
        results = cur.fetchall()

        for row, item in enumerate(results):
            print "Loading template from fingerprint reader for " + item[1] + " ..."

            try:
                fp.loadTemplate(int(item[3]), 0x01)
            except Exception as e:
                print "Failed to load template. " + str(e)
                continue

            try:
                template = json.dumps(fp.downloadCharacteristics(0x01))
                pass
            except Exception as e:
                print "Failed to download template. " + str(e)
                continue

            cur.execute(
                "UPDATE `karyawan` SET `template` = ? WHERE `id` = ?",
                (template, item[3])
            )
            print "Template saved to database!"

        cur.close()
        db.commit()

    def generate_uuid(self):
        cur = db.cursor()
        cur.execute("SELECT `id`, `nama` FROM `karyawan` WHERE `uuid` IS NULL")
        results = cur.fetchall()

        for row, item in enumerate(results):
            print "Generating UUID for " + item[1] + " ..."
            UUID = str(uuid.uuid4())
            cur.execute(
                "UPDATE `karyawan` SET `uuid` = ? WHERE `id` = ?",
                (UUID, item[0])
            )
            print "UUID saved to database!"

        cur.close()
        db.commit()
        print "Generate UUID completed!"

    def sync_user(self):
        confirm = raw_input("Anda yakin (y/n)? ")

        if confirm != 'y':
            return

        self.generate_uuid()
        self.save_template()

        cur = db.cursor()
        cur.execute("SELECT `id`, `nama`, `jabatan`, `fp_id`, `card_id`, `template`, `uuid` FROM `karyawan`")
        results = cur.fetchall()
        cur.close()

        for row, item in enumerate(results):
            data = {
                "nama": item[1],
                "jabatan": item[2],
                "fp_id": item[3],
                "card_id": item[4],
                "template": item[5],
                "uuid": item[6]
            }
            print "Syncing " + item[1] + "..."

            try:
                r = requests.post(config["api_url"] + "staff", data=data, timeout=3)
            except Exception as e:
                print "Sync staff data FAILED!" + str(e)
                continue

            if r.status_code == requests.codes.ok:
                try:
                    res = r.json()
                    print "Sync " + res["nama"] + " OK!"
                except Exception as e:
                    print "Sync staff data FAILED!" + str(e)
            else:
                print "Sync staff data FAILED! " + str(r.status_code)

    def buka_pintu(self):
        if GPIO.input(config["gpio_pin"]["sensor_pintu"]) != config["features"]["sensor_pintu"]["default_state"]:
            print "Pintu sudah terbuka"
        else:
            print "Silakan masuk..."
            GPIO.output(config["gpio_pin"]["relay"], 1)
            time.sleep(config["timer"]["open_duration"])
            GPIO.output(config["gpio_pin"]["relay"], 0)

    def check_memory_fp(self):
        print str(fp.getTemplateCount()) + '/' + str(fp.getStorageCapacity())

    def status_pintu(self):
        if GPIO.input(config["gpio_pin"]["sensor_pintu"]) == config["features"]["sensor_pintu"]["default_state"]:
            print "TERTUTUP"
        else:
            print "TERBUKA"

    def help(self):
        data = [
            ['PERINTAH', 'KETERANGAN'],
            ['?', 'Menampilkan pesan ini'],
            ['list', 'Menampilkan daftar semua staff di access door'],
            ['daftar', 'Mendaftarkan staff baru'],
            ['hapus', 'Menghapus staff'],
            ['log', 'Menampilkan log akses pintu'],
            ['clear log', 'Menghapus log'],
            ['clear database', 'Menghapus data staff dan log'],
            ['check memory fp', 'Check memory sensor finger print'],
            ['buka pintu', 'Buka pintu'],
            ['status pintu', 'Status pintu'],
            ['run', 'Menjalankan program akses pintu GUI'],
            ['save template', 'Menyimpan template sidik jari ke database'],
            ['generate uuid', 'Generate UUID'],
            ['sync user', 'Sync user data ke server'],
            ['exit', 'Keluar dari progam ini'],
            ['logout', 'Keluar dari program CLI']
        ]

        table = AsciiTable(data)
        print table.table

    def run(self):
        try:
            while True:
                cmd = raw_input("access_door> ")
                if cmd == "daftar":
                    self.daftar()
                elif cmd == "list":
                    self.list()
                elif cmd == "log":
                    self.log()
                elif cmd == "clear database":
                    self.clear_database()
                elif cmd == "clear log":
                    self.clear_log()
                elif cmd == "hapus":
                    self.hapus()
                elif cmd == "check memory fp":
                    self.check_memory_fp()
                elif cmd == "buka pintu":
                    self.buka_pintu()
                elif cmd == "status pintu":
                    self.status_pintu()
                elif cmd == "help" or cmd == "?":
                    self.help()
                elif cmd == "logout":
                    print "Bye"
                    break
                elif cmd == "exit" or cmd == "quit":
                    print "Bye"
                    exit()
                elif cmd == "run":
                    app = QtGui.QApplication(sys.argv)
                    ui = Main()
                    sys.exit(app.exec_())
                elif cmd == "save template":
                    self.save_template()
                elif cmd == "generate uuid":
                    self.generate_uuid()
                elif cmd == "sync user":
                    self.sync_user()
                elif cmd.strip():
                    print "Perintah tidak dikenal. Ketik '?' untuk bantuan."
                else:
                    pass

        except KeyboardInterrupt:
            print("Bye");
            exit(0)

def secs(start_time):
    dt = datetime.now() - start_time
    return dt.seconds

if __name__ == "__main__":
    log_file_path = os.path.join(os.path.dirname(__file__), 'access_door.log')
    config_file_path = os.path.join(os.path.dirname(__file__), 'config.json')

    log_level = {
        "NOTSET": 0,
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50
    }

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.RotatingFileHandler(log_file_path, maxBytes=1024000, backupCount=100)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.debug("Starting application...")

    try:
        logger.debug("Reading config file...")
        with open(config_file_path) as config_file:
            config = json.load(config_file)
    except Exception as e:
        message = "Gagal membuka file konfigurasi (config.json). " + str(e)
        logger.error(message)
        print message
        exit()

    use_nfc = False
    use_fp = False

    try:
        logger.debug("Initializing fingerprint reader...")
        fp = PyFingerprint(config["device"]["fp"], 57600, 0xFFFFFFFF, 0x00000000)

        if not fp.verifyPassword():
            message = 'Password fingerprint salah!'
            logger.error(message)
            print message

        logger.debug("Fingerprint reader OK!")
        use_fp = True

    except Exception as e:
        message = 'Gagal menginisialisasi fingerprint!' + str(e)
        logger.error(message)
        print message

    try:
        logger.debug("Initializing NFC Reader...")
        pn532 = PN532.PN532(config["device"]["nfc"], 115200)
        pn532.begin()
        pn532.SAM_configuration()
        logger.debug("NFC Reader OK!")
        use_nfc = True

    except Exception as e:
        message = "NFC Reader tidak ditemukan. " + str(e)
        logger.error(message)
        print message

    if not use_fp and not use_nfc:
        message = "Fingerprint reader dan NFC reader tidak ditemukan"
        logger.error(message)
        logger.debug("Exit")
        print message
        exit()

    if config["db"]["driver"] == "mysql":
        try:
            db = MySQLdb.connect(
                host=config["db"]["host"],
                user=config["db"]["user"],
                passwd=config["db"]["pass"],
                db=config["db"]["name"]
            )
            db.close()

        except Exception as e:
            message = "Gagal melakukan koneksi ke database. Cek konfigurasi database di config.json. " + str(e)
            logger.error(message)
            print message
            exit()

    elif config["db"]["driver"] == "sqlite":
        logger.debug("Connecting to database...")
        db = sqlite3.connect(os.path.join(os.path.dirname(__file__), config["db"]["name"]), check_same_thread=False)
        logger.debug("Creating database schema...")

        db.execute("CREATE TABLE IF NOT EXISTS `karyawan` ( \
            `id` INTEGER PRIMARY KEY AUTOINCREMENT, \
            `nama` varchar(30) NOT NULL, \
            `jabatan` varchar(30) NOT NULL, \
            `fp_id` varchar(20) NULL, \
            `fp_id1` varchar(20) NULL, \
            `card_id` varchar(20) NULL, \
            `template` text NULL, \
            `template1` text NULL, \
            `uuid` varchar(50) NULL, \
            `active` boolean default 1, \
            `last_update` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP, \
            `waktu_daftar` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)");

        db.execute("CREATE TABLE IF NOT EXISTS `log` ( \
            `id` INTEGER PRIMARY KEY AUTOINCREMENT, \
            `karyawan_id` int(11) NULL, \
            `waktu` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    else:
        message = "Koneksi database tidak dikenal (mysql/sqlite)"
        logger.error(message)
        print message
        exit()

    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(config["gpio_pin"]["relay"], GPIO.OUT)
    GPIO.setup(config["gpio_pin"]["alarm"], GPIO.OUT)
    GPIO.setup(config["gpio_pin"]["sensor_pintu"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(config["gpio_pin"]["saklar_manual"], GPIO.IN, pull_up_down=GPIO.PUD_UP)

    if len(sys.argv) > 1 and sys.argv[1] == "run":
        mixer.init()
        logger.debug("Starting GUI...")
        app = QtGui.QApplication(sys.argv)
        ui = Main()
        sys.exit(app.exec_())

    else:
        logger.debug("Starting console app...")
        console = Console()
        console.run()
