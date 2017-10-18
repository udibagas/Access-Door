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


class Main(QtGui.QWidget, main_ui.Ui_Form):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)

        self.update_clock()
        self.info.setText("TEMPELKAN JARI ATAU KARTU ANDA")
        self.showFullScreen()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)

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
        terlalu_lama = False
        start_time = datetime.now()

        if config["features"]["sensor_pintu"]:
            while GPIO.input(config["gpio_pin"]["sensor_pintu"]):
                time.sleep(0.2)
                if secs(start_time) > 3:
                    terlalu_lama = True
                    break

        if terlalu_lama:
            GPIO.output(config["gpio_pin"]["relay"], 0)
            message = "WAKTU HABIS"
            self.info.setText(message)
            logger.info(message)
            time.sleep(2)
            message = "TEMPELKAN JARI ATAU KARTU ANDA"
            self.info.setText(message)
            return

        if karyawan:
            cur = db.cursor()
            cur.execute("INSERT INTO `log` (`karyawan_id`) VALUES (?)", (karyawan[0],))
            cur.close()
            db.commit()

        # simpan log ke server (buka)
        try:
            logger.debug("Mengirim log ke server")
            data = {'access_by': nama, 'status': 0}
            r = requests.post(config["api_url"], data=data)
        except Exception as e:
            logger.debug("Koneksi ke server gagal")

        # kasih jeda 5 detik biar masuk
        time.sleep(config["timer"]["open_duration"])

        if config["features"]["sensor_pintu"]:
            while not GPIO.input(config["gpio_pin"]["sensor_pintu"]):
                message = "MOHON TUTUP PINTU"
                self.info.setText(message)
                logger.info(message)
                time.sleep(1)

        # tutup pintu
        GPIO.output(config["gpio_pin"]["relay"], 0)

        # simpan log ke server (tutup)
        try:
            logger.debug("Mengirim log ke server")
            data = {'access_by': nama, 'status': 1}
            r = requests.post(config["api_url"], data=data)
        except Exception as e:
            logger.warning("Koneksi ke server gagal")

        message = "TEMPELKAN JARI ATAU KARTU ANDA"
        self.info.setText(message)
        logger.info(message)


class ScanCardThread(QtCore.QThread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.exiting = False

    def __del__(self):
        self.exiting = True
        self.wait()

    def run(self):
        while not self.exiting:
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

            if not result:
                message = "KARTU TIDAK TERDAFTAR"
                self.emit(QtCore.SIGNAL('updateInfo'), message)
                logger.info(message)
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
            if GPIO.input(config["gpio_pin"]["sensor_pintu"]) and not GPIO.input(config["gpio_pin"]["saklar_manual"]):
                ui.buka_pintu()
            else:
                time.sleep(0.2)


class ScanFingerThread(QtCore.QThread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.exiting = False

    def __del__(self):
        self.exiting = True
        self.wait()

    def read_image(self):
        while not fp.readImage():
            time.sleep(0.5)

    def run(self):
        while not self.exiting:
            try:
                self.read_image()
            except Exception as e:
                continue

            fp.convertImage(0x01)
            result = fp.searchTemplate()
            fp_id = result[0]

            if fp_id == -1:
                logger.info("Sidik jari tidak ditemukan")
                self.emit(QtCore.SIGNAL('updateInfo'), "SIDIK JARI TIDAK DITEMUKAN")
                time.sleep(2)
                continue

            cur = db.cursor()
            cur.execute("SELECT * FROM karyawan WHERE `fp_id` = ?", (fp_id,))
            result = cur.fetchone()
            cur.close()

            if not result:
                logger.info("Sidik jari tidak terdaftar")
                self.emit(QtCore.SIGNAL('updateInfo'), "ANDA TIDAK TERDAFTAR")
                time.sleep(2)
                continue

            ui.buka_pintu(result)

class Console():
    def __init__(self):
        pass

    def daftar(self):
        nama = raw_input("NAMA: ")
        jabatan = raw_input("JABATAN: ")
        card_id = None
        fp_id = None

        if not nama or not jabatan:
            print "Nama dan jabatan harus diisi. Silakan ulangi kembali"
            return

        if use_fp:
            print('Tempelkan jari Anda...')

            while not fp.readImage():
                time.sleep(0.5)

            fp.convertImage(0x01)
            result = fp.searchTemplate()
            positionNumber = result[0]

            if positionNumber >= 0:
                print('Jari sudah terdaftar. Silakan ulangi kembali')
                return

            print('Angkat jari...')
            time.sleep(2)

            print('Tempelkan jari yang sama...')
            while not fp.readImage():
                time.sleep(0.5)

            fp.convertImage(0x02)

            if fp.compareCharacteristics() == 0:
                print "Sidik jari tidak sama. Silakan ulangi kembali"
                return

            fp.createTemplate()
            fp_id = fp.storeTemplate()

        if use_nfc:
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
                fp.deleteTemplate(fp_id)
                return

        cur = db.cursor()
        cur.execute(
            "INSERT INTO `karyawan` (`nama`, `jabatan`, `fp_id`, `card_id`) VALUES (?, ?, ?, ?)",
            (nama, jabatan, fp_id, card_id)
        )
        cur.close()
        db.commit()

        print "Pendaftaran BERHASIL!"

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
        if confirm == "y":
            cur = db.cursor()
            cur.execute("DELETE FROM `karyawan`")
            cur.execute("DELETE FROM `log`")
            cur.close()
            db.commit()
            fp.clearDatabase()

    def clear_log(self):
        confirm = raw_input("Anda yakin (y/N)? ")
        if confirm == "y":
            cur = db.cursor()
            cur.execute("DELETE FROM `log`")
            cur.close()
            db.commit()

    def hapus(self):
        id_karyawan = raw_input("Masukkan ID yang akan Anda hapus: ")

        if not id_karyawan:
            return

        cur = db.cursor()
        cur.execute("SELECT * FROM `karyawan` WHERE id = ?", (id_karyawan,))
        result = cur.fetchone()
        cur.close()

        if not result:
            print "ID karyawan tidak ditemukan. Silakan ketik 'list' untuk menampilkan data semua karyawan."
            return

        data = [
            ["ID", "NAMA", "JABATAN", "FINGERPRINT ID", "CARD ID", "WAKTU DAFTAR"],
            [str(result[0]), result[1], result[2], result[3], result[4], result[5]]
        ]

        table = AsciiTable(data)
        print table.table
        confirm = raw_input("Anda yakin akan menghapus karyawan ini (y/n)?")

        if confirm == "y" or confirm == "Y":
            cur = db.cursor()
            cur.execute("DELETE FROM `karyawan` WHERE id = ?", (id_karyawan,))
            cur.close()
            db.commit()
            print "Data karyawan berhasil dihapus"
            fp.delete(int(result[3]))

    def open_door(self):
        if not GPIO.input(config["gpio_pin"]["sensor_pintu"]):
            print "Pintu sudah terbuka"
        else:
            GPIO.output(config["gpio_pin"]["relay"], 1)
            time.sleep(config["timer"]["open_duration"])
            GPIO.output(config["gpio_pin"]["relay"], 0)

    def check_memory_fp(self):
        print str(fp.getTemplateCount()) + '/' + str(fp.getStorageCapacity())

    def status_pintu(self):
        if GPIO.input(config["gpio_pin"]["sensor_pintu"]):
            print "TERTUTUP"
        else:
            print "TERBUKA"

    def help(self):
        data = [
            ['PERINTAH', 'KETERANGAN'],
            ['?', 'Menampilkan pesan ini'],
            ['list', 'Daftar semua karyawan'],
            ['daftar', 'Mendaftarkan karyawan baru'],
            ['hapus', 'Menghapus karyawan'],
            ['log', 'Menampilkan log akses pintu'],
            ['clear log', 'Menghapus log'],
            ['clear database', 'Menghapus data karyawan dan log'],
            ['check memory fp', 'Check memory sensor finger print'],
            ['buka pintu', 'Buka pintu'],
            ['status pintu', 'Status pintu'],
            ['run', 'Menjalankan program akses pintu GUI'],
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

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.RotatingFileHandler(log_file_path, maxBytes=102400, backupCount=100)
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

        logger.debug("Fingerprint reader initialized!")
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
        logger.debug("NFC Reader initialized!")
        use_nfc = True
    except Exception as e:
        message = "NFC Reader tidak ditemukan"
        logger.error(message)
        print message

    if not use_fp and not use_nfc:
        message = "Fingerprint sensor dan NFC Reader tidak ditemukan"
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
            `fp_id` varchar(20) NULL, \
            `card_id` varchar(20) NULL, \
            `template` text NULL, \
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
    GPIO.setup(config["gpio_pin"]["sensor_pintu"], GPIO.IN , pull_up_down=GPIO.PUD_UP)
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
