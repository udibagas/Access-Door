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


class Main(QtGui.QWidget, main_ui.Ui_Form):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)

        self.update_clock()
        self.info.setText("TEMPELKAN JARI ATAU KARTU ANDA")
        self.instansi.setText(config["instansi"])
        self.logo.setPixmap(QtGui.QPixmap(config["logo"]))
        self.showFullScreen()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)

        # timer untuk sync user
        self.timer_sync = QtCore.QTimer()
        self.timer_sync.timeout.connect(self.sync_user)
        self.timer_sync.start(5000)

        if use_fp:
            self.scan_finger_thread = ScanFingerThread()
            self.connect(self.scan_finger_thread, QtCore.SIGNAL('updateInfo'), self.update_info)
            self.connect(self.scan_finger_thread, QtCore.SIGNAL('bukaPintu'), self.buka_pintu)
            self.scan_finger_thread.start()

        if use_nfc:
            self.scan_card_thread = ScanCardThread()
            self.connect(self.scan_card_thread, QtCore.SIGNAL('updateInfo'), self.update_info)
            self.connect(self.scan_card_thread, QtCore.SIGNAL('bukaPintu'), self.buka_pintu)
            self.scan_card_thread.start()

        self.open_manual_thread = OpenManualThread()
        self.connect(self.open_manual_thread, QtCore.SIGNAL('bukaPintu'), self.buka_pintu)
        self.open_manual_thread.start()

    def update_info(self, info):
        self.info.setText(info)

    def sync_user(self):
        try:
            r = requests.get(config["api_url"] + "akses/sync")
        except Exception as e:
            logger.info("Failed to sync user." + str(e))
            return

        if r.status_code == requests.codes.ok:
            try:
                users = r.json()
            except Exception as e:
                logger.info("Failed to sync user. " + str(e))
                return

        if len(users) == 0:
            logger.info("No data from server")
            return

        cur = db.cursor()
        cur.execute("SELECT `uuid` FROM `karyawan`")
        results = cur.fetchall()
        cur.close()

        uuids = []
        for row, item enumerate(results)
            uuids.append(item[0])

        server_uuids = []

        # tambah user kalau ada yang baru
        for row, item in enumerate(users):
            server_uuids.append(item["uuid"])

            # kalau sudah ada update saja data nama & jabatan barangkali berubah
            logger.info("Updating local database...")
            if item["uuid"] in uuids:
                cur = db.cursor()
                cur.execute("UPDATE `karyawan` SET `nama` = ?, `jabatan` = ? WHERE `uuid` = ?", (item["nama"], item["jabatan"], item["uuid"]))
                cur.close()
                db.commit()

            logger.info("Add user to local database...")

            try:
                cur = db.cursor()
                cur.execute(
                    "INSERT INTO `karyawan` (`nama`, `jabatan`, `fp_id`, `card_id`, `template`, `uuid`) VALUES (?, ?, ?, ?, ?, ?)",
                    (item["nama"], item["jabatan"], "***", item["card_id"], item["template"], item["uuid"])
                )
                cur.close()
                db.commit()
            except Exception as e:
                logger.info("Saving to local database FAILED! " + str(e))
                continue

            logger.info("Saving to local database SUCCESS!")

        # hapus user kalau ada yg dihapus
        for i in uuids:
            if i not in server_uuids:
                logger.info("Deleting user with uuid " + i)
                cur = db.cursor()
                cur.execute("DELETE FROM `karyawan` WHERE `uuid` = ?", (i,))
                cur.close()
                db.commit()

    def update_clock(self):
        self.tanggal.setText(time.strftime("%d %b %Y"))
        self.jam.setText(time.strftime("%H:%M:%S"))

    def buka_pintu(self, karyawan=None):
        if karyawan:
            nama = karyawan[1].upper()
        else:
            nama = ""

        message = "SILAKAN MASUK " + nama
        self.info.setText(message)
        logger.info(message)

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
            time.sleep(2)
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
            r = requests.post(config["api_url"] + "logPintu", data=data)
        except Exception as e:
            logger.warning("GAGAL mengirim log ke server")

        if r.status_code == requests.codes.ok:
            logger.info("SUKSES mengirim log ke server")
        else:
            logger.warning("GAGAL mengirim log ke server")

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
                    alarm = True

                time.sleep(0.2)

        else:
            time.sleep(config["timer"]["open_duration"])

        # turn off alarm
        if alarm:
            GPIO.output(config["gpio_pin"]["alarm"], 0)
        # tutup pintu
        GPIO.output(config["gpio_pin"]["relay"], 0)

        # simpan log ke server (tutup)
        if nama == "":
            nama = "MANUAL"
        data = {'access_by': nama, 'status': 1}

        try:
            r = requests.post(config["api_url"] + "logPintu", data=data)
        except Exception as e:
            logger.warning("GAGAL mengirim log ke server")

        if r.status_code == requests.codes.ok:
            logger.info("SUKSES mengirim log ke server")
        else:
            logger.warning("GAGAL mengirim log ke server")

        self.info.setText("TEMPELKAN JARI ATAU KARTU ANDA")


class ScanCardThread(QtCore.QThread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.exiting = False

    def __del__(self):
        self.exiting = True
        self.wait()

    def run(self):
        while not self.exiting:
            self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ATAU KARTU ANDA")
            try:
                uid = pn532.read_passive_target()
            except Exception as e:
                self.emit(QtCore.SIGNAL('updateInfo'), "GAGAL MEMBACA KARTU")
                time.sleep(2)
                continue

            if uid is "no_card":
                continue

            card_id = str(binascii.hexlify(uid))

            cur = db.cursor()
            cur.execute("SELECT * FROM karyawan WHERE `card_id` = ?", (card_id,))
            result = cur.fetchone()
            cur.close()

            if result:
                ui.buka_pintu(result)
            else:
                self.emit(QtCore.SIGNAL('updateInfo'), "KARTU TIDAK TERDAFTAR")
                time.sleep(2)


class ScanFingerThread(QtCore.QThread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.exiting = False

    def __del__(self):
        self.exiting = True
        self.wait()

    def read_image(self):
        while not fp.readImage():
            time.sleep(0.2)

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

    def run(self):
        while not self.exiting:
            self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ATAU KARTU ANDA")
            try:
                self.read_image()
            except Exception as e:
                continue

            try:
                fp.convertImage(0x01)
            except Exception as e:
                logger.info("Failed to convert image. " + str(e))
                continue

            try:
                result = fp.searchTemplate()
            except Exception as e:
                logger.info("Failed to search template. " + str(e))
                continue

            fp_id = result[0]

            # kalau di fingerprint reader tidak ketemu cari di database barangkali ada
            if fp_id == -1:
                try:
                    template = json.dumps(fp.downloadCharacteristics(0x01))
                except Exception as e:
                    logger.info("Failed to download characteristics. " + str(e))
                    self.emit(QtCore.SIGNAL('updateInfo'), "SIDIK JARI TIDAK DITEMUKAN")
                    continue

                cur = db.cursor()
                cur.execute("SELECT * FROM `karyawan` WHERE `template` = ?", (template,))
                result = cur.fetchone()
                cur.close()

                if not result:
                    self.emit(QtCore.SIGNAL('updateInfo'), "SIDIK JARI TIDAK DITEMUKAN")
                    time.sleep(2)
                    continue

                fp_id = self.save_template(template)

                if fp_id >= 0:
                    cur = db.cursor()
                    cur.execute("UPDATE `karyawan` SET `fp_id` = ? WHERE id = ?", (fp_id, result[0]))
                    cur.close()
                    db.commit()
                    ui.buka_pintu(result)
                    continue

            cur = db.cursor()
            cur.execute("SELECT * FROM karyawan WHERE `fp_id` = ?", (fp_id,))
            result = cur.fetchone()
            cur.close()

            if not result:
                self.emit(QtCore.SIGNAL('updateInfo'), "ANDA TIDAK TERDAFTAR")
                time.sleep(2)
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
                logger.info("Open by switch")
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
                time.sleep(0.2)

            try:
                fp.convertImage(0x01)
            except Exception as e:
                print "Error convert image on buffer 0x01. " + str(e)
                break

            try:
                result = fp.searchTemplate()
            except Exception as e:
                print "Error search template. " + str(e)
                break

            positionNumber = result[0]

            if positionNumber >= 0:
                print('Jari sudah terdaftar. Silakan ulangi kembali')
                break

            print('Angkat jari...')
            time.sleep(2)

            print('Tempelkan jari yang sama...')
            while not fp.readImage():
                time.sleep(0.2)

            try:
                fp.convertImage(0x02)
            except Exception as e:
                print "Error convert image on buffer 0x02. " + str(e)
                break

            if not fp.compareCharacteristics():
                print "Sidik jari tidak sama. Silakan ulangi kembali"
                break

            try:
                fp.createTemplate()
            except Exception as e:
                print "Failed to create template. " + str(e)
                break

            try:
                fp_id = fp.storeTemplate()
            except Exception as e:
                print "Failed to store template." + str(e)
                break

            try:
                fp.loadTemplate(fp_id, 0x01)
            except Exception as e:
                print "Failed to load template." + str(e)
                break

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

                break

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
            r = requests.post(config["api_url"] + "staff", data=data)
        except Exception as e:
            print "Sync staff data FAILED!" + str(e)
            return

        if r.status_code == requests.codes.ok:
            print "Sync staff data OK!"
        else:
            print "Sync staff data FAILED!" + r.text

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

    def get_data_from_server(self):
        try:
            r = requests.get(config["api_url"] + "staff")
        except Exception as e:
            raise Exception("Koneksi ke server gagal. " + str(e))
            return False

        if r.status_code == requests.codes.ok:
            try:
                return r.json()
            except Exception as e:
                raise Exception("Invalid JSON. " + str(e))
                return False
        else:
            raise Exception("Koneksi ke server error. " + str(r.text))
            return False

    def list_server(self):
        data = [["ID", "NAMA", "JABATAN", "CARD ID", "WAKTU DAFTAR"]]

        try:
            staff = self.get_data_from_server()
        except Exception as e:
            print str(e)
            return

        for row, item in enumerate(staff):
            data.append([int(item["id"]), item["nama"], item["jabatan"], item["card_id"], item["created_at"]])

        table = AsciiTable(data)
        print table.table

    def assign(self):
        data = [["ID", "NAMA", "JABATAN", "CARD ID", "WAKTU DAFTAR"]]

        cur = db.cursor()
        cur.execute("SELECT `uuid` FROM `karyawan`")
        results = cur.fetchall()
        cur.close()

        uuids = []
        for row, item enumerate(results)
            uuids.append(item[0])

        try:
            staff = self.get_data_from_server()
        except Exception as e:
            print str(e)
            return

        for row, item in enumerate(staff):
            if item["uuid"] in uuids:
                continue
            data.append([int(item["id"]), item["nama"], item["jabatan"], item["card_id"], item["created_at"]])

        table = AsciiTable(data)
        print table.table

        staff_id = raw_input("Masukkan ID staff yang akan di assign: ")
        fp_id = "***"

        try:
            staff_id = int(staff_id)
        except Exception as e:
            print "ID yang anda masukkan salah " + str(e)
            return

        try:
            r = requests.get(config["api_url"] + "staff/" + str(staff_id))
        except Exception as e:
            print "Koneksi ke server GAGAL. " + str(e)
            return

        try:
            staff = r.json()
        except Exception as e:
            print "Invalid JSON. " + str(e)
            return

        cur = db.cursor()
        cur.execute("SELECT `nama` FROM `karyawan` WHERE `uuid` = ?", (staff["uuid"],))
        result = cur.fetchone()

        if result:
            print result[0] + " sudah terdaftar."
            cur.close()
            return

        if staff["template"] == "":
            print "Template sidik jari tidak ditemukan."

        else:
            print "Saving template to fingerprint reader..."

            try:
                template = json.loads(staff["template"])
            except Exception as e:
                print "Template error. Invalid JSON"
                return

            try:
                fp.uploadCharacteristics(0x01, template)
            except Exception as e:
                print "Failed to upload template to fingerprint reader. " + str(e)
                return

            try:
                fp_id = fp.storeTemplate()
            except Exception as e:
                print "Failed to store template to fingerprint reader. " + str(e)
                return

            print "Fingerprint template saved to #" + str(fp_id)

        print "Saving to local database..."

        try:
            cur.execute(
                "INSERT INTO `karyawan` (`nama`, `jabatan`, `fp_id`, `card_id`, `template`, `uuid`) VALUES (?, ?, ?, ?, ?, ?)",
                (staff["nama"], staff["jabatan"], fp_id, staff["card_id"], staff["template"], staff["uuid"])
            )
            cur.close()
            db.commit()
        except Exception as e:
            print "Saving to local database FAILED! " + str(e)
            print "Deleting template... "
            try:
                fp.deleteTemplate(fp_id)
            except Exception as e:
                print "Failed to delete template. Please delete it manually. " + str(e)

        print "Saving to local database SUCCESS!"

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
                r = requests.post(config["api_url"] + "staff", data=data)
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
                print "Sync staff data FAILED!" + r.text

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
            ['list server', 'Menampilkan daftar semua staff di sever'],
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
            ['assing', 'Assign user from server to access door'],
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
                elif cmd == "list server":
                    self.list_server()
                elif cmd == "assign":
                    self.assign()
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

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

if __name__ == "__main__":
    log_file_path = os.path.join(os.path.dirname(__file__), 'access_door.log')
    config_file_path = os.path.join(os.path.dirname(__file__), 'config.json')

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
        message = "Gagal membuka file konfigurasi (config.json)"
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
        message = "NFC Reader tidak ditemukan"
        logger.error(message)
        print message

    if not use_fp and not use_nfc:
        message = "Fingerprint reader dan NFC reader tidak ditemukan"
        logger.error(message)
        logger.info("Exit")
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
            message = "Gagal melakukan koneksi ke database. Cek konfigurasi database di config.json"
            logger.error(message)
            print message
            exit()

    elif config["db"]["driver"] == "sqlite":
        logger.debug("Connecting to database...")
        db = sqlite3.connect(config["db"]["name"], check_same_thread=False)
        logger.debug("Creating database schema...")

        db.execute("CREATE TABLE IF NOT EXISTS `karyawan` ( \
            `id` INTEGER PRIMARY KEY AUTOINCREMENT, \
            `nama` varchar(30) NOT NULL, \
            `jabatan` varchar(30) NOT NULL, \
            `fp_id1` varchar(20) NULL, \
            `fp_id2` varchar(20) NULL, \
            `card_id` varchar(20) NULL, \
            `template1` text NULL, \
            `template2` text NULL, \
            `uuid` varchar(50) NULL, \
            `active` boolean default 1, \
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
        logger.debug("Starting GUI...")
        app = QtGui.QApplication(sys.argv)
        ui = Main()
        sys.exit(app.exec_())

    else:
        logger.debug("Starting console app...")
        console = Console()
        console.run()
