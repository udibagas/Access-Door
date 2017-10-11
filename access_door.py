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


class Main(QtGui.QWidget, main_ui.Ui_Form):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)

        self.update_clock()
        self.update_info("TEMPELKAN JARI ANDA")
        self.showFullScreen()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)

        self.scan_thread = ScanThread()
        self.connect(self.scan_thread, QtCore.SIGNAL('updateInfo'), self.update_info)
        self.scan_thread.start()

    def update_info(self, info):
        self.info.setText(info)

    def update_clock(self):
        self.tanggal.setText(time.strftime("%d %b %Y"))
        self.jam.setText(time.strftime("%H:%M:%S"))


class ScanThread(QtCore.QThread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.exiting = False

    def __del__(self):
        self.exiting = True
        self.wait()

    def read_card(self):
        start_time = datetime.now()

        while not self.exiting:
            if secs(start_time) > 10:
                self.emit(QtCore.SIGNAL('updateInfo'), "WAKTU HABIS")
                time.sleep(2)
                return False

            uid = nfc.pn532.read_passive_target()
            if uid is "no_card":
                continue

            return str(binascii.hexlify(uid))

    # buka manual masih sala sepertinya
    def buka_manual(self):
        self.emit(QtCore.SIGNAL('updateInfo'), "SILAKAN MASUK")
        GPIO.output(pin_buka_pintu, 1)
        terlalu_lama = False
        start_time = datetime.now()

        if sensor_pintu_exists:
            while GPIO.input(pin_status_pintu):
                time.sleep(0.2)
                if secs(start_time) > 3:
                    terlalu_lama = True
                    break

        # ga jadi dibuka
        if terlalu_lama:
            GPIO.output(pin_buka_pintu, 0)
            self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ANDA")
            return

        # jadi dibuka
        try:
            data = {'ip_address': ip_address, 'access_by': 'manual', 'status': 0}
            r = requests.post(api_url, data=data)
        except Exception as e:
            pass

        # kasih jeda 5 detik biar masuk
        time.sleep(5)

        if sensor_pintu_exists:
            while not GPIO.input(pin_status_pintu):
                self.emit(QtCore.SIGNAL('updateInfo'), "MOHON TUTUP PINTU")
                time.sleep(1)

        GPIO.output(pin_buka_pintu, 0)

        try:
            data = {'ip_address': ip_address, 'access_by': 'manual', 'status': 1}
            r = requests.post(api_url, data=data)
        except Exception as e:
            pass

        self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ANDA")

    def read_image(self):
        while not fp.fp.readImage():
            # jika pintu tertutup dan ada yang neken saklar buka manual
            if GPIO.input(pin_status_pintu) and not GPIO.input(pin_buka_manual):
                self.buka_manual()

            else:
                time.sleep(0.5)

    def run(self):
        self.emit(QtCore.SIGNAL('updateInfo'), "MOHON TUNGGU...")
        time.sleep(5)
        while not self.exiting:
            self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ANDA")

            try:
                self.read_image()
            except Exception as e:
                continue

            fp.fp.convertImage(0x01)
            result = fp.fp.searchTemplate()
            fp_id = result[0]

            if fp_id == -1:
                self.emit(QtCore.SIGNAL('updateInfo'), "SIDIK JARI TIDAK DITEMUKAN")
                time.sleep(2)
                continue

            self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN KARTU")

            if use_nfc:
                try:
                    card_id = self.read_card()
                except Exception as e:
                    self.emit(QtCore.SIGNAL('updateInfo'), "GAGAL MEMBACA KARTU")
                    time.sleep(2)
                    continue

                if not card_id:
                    continue

            cur = db_con.cursor()

            if use_nfc:
                cur.execute("SELECT * FROM karyawan WHERE `fp_id` = ? AND `card_id` = ?", (fp_id, card_id))
            else:
                cur.execute("SELECT * FROM karyawan WHERE `fp_id` = ?", (fp_id,))

            result = cur.fetchone()
            cur.close()

            if not result:
                if use_nfc:
                    self.emit(QtCore.SIGNAL('updateInfo'), "SIDIK JARI DAN KARTU TIDAK COCOK")
                else:
                    self.emit(QtCore.SIGNAL('updateInfo'), "ANDA TIDAK TERDAFTAR")
                time.sleep(2)
                continue

            self.emit(QtCore.SIGNAL('updateInfo'), "SILAKAN MASUK, " + result[1].upper())
            GPIO.output(pin_buka_pintu, 1)
            terlalu_lama = False
            start_time = datetime.now()

            if sensor_pintu_exists:
                while GPIO.input(pin_status_pintu):
                    time.sleep(0.2)
                    if secs(start_time) > 3:
                        terlalu_lama = True
                        break

            if terlalu_lama:
                GPIO.output(pin_buka_pintu, 0)
                self.emit(QtCore.SIGNAL('updateInfo'), "WAKTU HABIS")
                time.sleep(2)
                continue

            cur = db_con.cursor()
            cur.execute("INSERT INTO `log` (`karyawan_id`) VALUES (?)", (result[0],))
            cur.close()
            db_con.commit()

            # simpan log ke server (buka)
            try:
                data = {'ip_address': ip_address, 'access_by': result[1], 'status': 0}
                r = requests.post(api_url, data=data)
            except Exception as e:
                pass

            # kasih jeda 5 detik biar masuk
            time.sleep(5)

            if sensor_pintu_exists:
                while not GPIO.input(pin_status_pintu):
                    self.emit(QtCore.SIGNAL('updateInfo'), "MOHON TUTUP PINTU")
                    time.sleep(1)

            GPIO.output(pin_buka_pintu, 0)

            # simpan log ke server (tutup)
            try:
                data = {'ip_address': ip_address, 'access_by': result[1], 'status': 1}
                r = requests.post(api_url, data=data)
            except Exception as e:
                pass

class FP():
    def __init__(self, device):
        self.device = device

        try:
            self.fp = PyFingerprint(self.device, 57600, 0xFFFFFFFF, 0x00000000)

            if not self.fp.verifyPassword():
                print 'Password fingerprint salah!'
                exit(0)

        except Exception as e:
            print('Gagal menginisialisasi fingerprint!')
            print('Pesan kesalahan: ' + str(e))
            exit(0)

    def scan(self):
        while not self.fp.readImage():
            time.sleep(1)

        self.fp.convertImage(0x01)
        result = self.fp.searchTemplate()
        fp_id = result[0]

        if fp_id >= 0:
            print "Sidik jari ditemukan pada #" + str(fp_id)
            return fp_id

        else:
            print "Jari tidak terdaftar"
            return -1

    def delete(self, position):
        if self.fp.deleteTemplate(position):
            print "Template sidik jari berhasil dihapus"
            return True

        else:
            print "Template sidik jari #" + position + " gagal dihapus"
            return False

    def clear_database(self):
        self.fp.clearDatabase();

    def check_memory(self):
        print('Template terpakai saat ini: ' + str(self.fp.getTemplateCount()) + '/' + str(self.fp.getStorageCapacity()))

    def enroll(self):
        ## Informasi fingerprint
        print('Template terpakai saat ini: ' + str(self.fp.getTemplateCount()) + '/' + str(self.fp.getStorageCapacity()))
        ## Enroll jari
        print('Tempelkan jari Anda...')

        while not self.fp.readImage():
            time.sleep(0.5)

        self.fp.convertImage(0x01)
        result = self.fp.searchTemplate()
        positionNumber = result[0]

        if positionNumber >= 0:
            print('Jari sudah terdaftar pada #' + str(positionNumber)) + ". Silakan ulangi kembali"
            return -1

        else:
            print('Angkat jari...')
            time.sleep(2)

            print('Tempelkan jari yang sama...')
            while not self.fp.readImage():
                time.sleep(0.5)

            self.fp.convertImage(0x02)

            ## Bandingkan jari
            if self.fp.compareCharacteristics() == 0:
                print "Sidik jari tidak sama. Silakan ulangi kembali"
                return -1

            else:
                ## Buat template
                self.fp.createTemplate()
                ## Simpan template
                fp_id = self.fp.storeTemplate()
                # print('Sidik jari berhasil di daftarkan!')
                # print('Template baru pada #' + str(fp_id))
                # untuk disimpan di database
                return fp_id

class NFC():
    def __init__(self, device):
        self.device = device
        self.pn532 = PN532.PN532(self.device, 115200)
        self.pn532.begin()
        self.pn532.SAM_configuration()
        # Get the firmware version from the chip and print(it out.)
        ic, ver, rev, support = self.pn532.get_firmware_version()

    def scan(self):
        while True:
            uid = self.pn532.read_passive_target()
            if uid is "no_card":
                continue

            return str(binascii.hexlify(uid))

def secs(start_time):
    dt = datetime.now() - start_time
    return dt.seconds


if __name__ == "__main__":
    # db_con = MySQLdb.connect(host="localhost", user="root", passwd="bismillah", db="access_door")
    db_con = sqlite3.connect("access_door.db", check_same_thread = False)

    # populate db
    db_con.execute("CREATE TABLE IF NOT EXISTS `karyawan` ( \
        `id` INTEGER PRIMARY KEY AUTOINCREMENT, \
        `nama` varchar(30) NOT NULL, \
        `jabatan` varchar(30) NOT NULL, \
        `fp_id` varchar(20) NOT NULL, \
        `card_id` varchar(20) NULL, \
        `waktu_daftar` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)");

    db_con.execute("CREATE TABLE IF NOT EXISTS `log` ( \
        `id` INTEGER PRIMARY KEY AUTOINCREMENT, \
        `karyawan_id` int(11) NOT NULL, \
        `waktu` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    ip_address = "192.168.99.208"
    api_url = "http://192.168.99.150/smading/api/logPintu"

    use_nfc = False
    sensor_pintu_exists = False
    fp = FP("/dev/serial1")

    try:
        nfc = NFC("/dev/serial2")
        use_nfc = True
    except Exception as e:
        pass

    # PIN pada raspberry
    pin_buka_pintu = 36  # untuk trigger buka pintu
    pin_status_pintu = 38
    pin_buka_manual = 40

    # inisiasi GPIO pada raspberry
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(pin_buka_pintu, GPIO.OUT)
    GPIO.setup(pin_status_pintu, GPIO.IN , pull_up_down=GPIO.PUD_UP)
    GPIO.setup(pin_buka_manual, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    if len(sys.argv) > 1 and sys.argv[1] == "run":
        app = QtGui.QApplication(sys.argv)
        ui = Main()
        sys.exit(app.exec_())

    else:
        while True:
            try:
                cmd = raw_input("access_door> ")

                # UNTUK MENDAFTARKAN KARYAWAN BARU
                if cmd == "daftar":
                    nama = raw_input("NAMA \t\t: ")
                    jabatan = raw_input("JABATAN \t: ")

                    if not nama or not jabatan:
                        print "Nama dan jabatan harus diisi. Silakan ulangi kembali"
                        continue

                    # enroll sidik jari
                    fp_id = fp.enroll()

                    # keluar loop kalau sudah pernah terdaftar
                    if fp_id < 0:
                        continue

                    if use_nfc:
                        # scan kartu
                        print "Tempelkan kartu..."
                        card_id = nfc.scan()

                        # cek apakah kartu sudah pernah terdaftar
                        cur = db_con.cursor()
                        cur.execute("SELECT * FROM `karyawan` WHERE card_id = ?", (card_id,))
                        result = cur.fetchone()
                        cur.close()

                        if result:
                            print "Kartu sudah terdaftar atas nama " + result[1]
                            # hapus template yang sudah tersimpan
                            fp.delete(fp_id)
                            continue

                    cur = db_con.cursor()

                    if use_nfc:
                        cur.execute("INSERT INTO `karyawan` (`nama`, `jabatan`, `fp_id`, `card_id`) VALUES (?, ?, ?, ?)", (nama, jabatan, fp_id, card_id))
                    else:
                        cur.execute("INSERT INTO `karyawan` (`nama`, `jabatan`, `fp_id`) VALUES (?, ?, ?)", (nama, jabatan, fp_id))

                    cur.close()
                    db_con.commit()

                    print "Pendaftaran BERHASIL!"

                # UNTUK MELIHAT DAFTAR SEMUA KARYAWAN
                elif cmd == "list":
                    cur = db_con.cursor()
                    cur.execute("SELECT `id`, `nama`, `jabatan`, `fp_id`, `card_id`, datetime(`waktu_daftar`, 'localtime') FROM `karyawan` ORDER BY `nama` ASC")
                    result = cur.fetchall()
                    cur.close()

                    data = [["ID", "NAMA", "JABATAN", "FINGERPRINT ID", "CARD ID", "WAKTU DAFTAR"]]

                    for row, item in enumerate(result):
                        data.append([str(item[0]), item[1], item[2], item[3], item[4], item[5]])

                    table = AsciiTable(data)
                    print table.table

                # UNTUK MELIHAT LOG KARYAWAN MASUK
                elif cmd == "log":
                    cur = db_con.cursor()
                    cur.execute("SELECT datetime(`log`.`waktu`, 'localtime'), `karyawan`.`nama`, `karyawan`.`jabatan` FROM `log` LEFT JOIN `karyawan` ON `karyawan`.`id` = `log`.`karyawan_id` ORDER BY `log`.`waktu` ASC")
                    result = cur.fetchall()
                    cur.close()

                    data = [["WAKTU MASUK", "NAMA", "JABATAN"]]

                    for row, item in enumerate(result):
                        data.append([str(item[0]), item[1], item[2]])

                    table = AsciiTable(data)
                    print table.table

                elif cmd == "clear database":
                    confirm = raw_input("Anda yakin (y/N)? ")
                    if confirm == "y":
                        cur = db_con.cursor()
                        cur.execute("DELETE FROM `karyawan`")
                        cur.execute("DELETE FROM `log`")
                        cur.close()
                        db_con.commit()
                        fp.clear_database()

                elif cmd == "clear log":
                    confirm = raw_input("Anda yakin (y/N)? ")
                    if confirm == "y":
                        cur = db_con.cursor()
                        cur.execute("DELETE FROM `log`")
                        cur.close()
                        db_con.commit()

                # UNTUK MENGHAPUS DATA KARYAWAN
                elif cmd == "hapus":
                    id_karyawan = raw_input("Masukkan ID yang akan Anda hapus: ")

                    if not id_karyawan:
                        continue

                    cur = db_con.cursor()
                    cur.execute("SELECT * FROM `karyawan` WHERE id = ?", (id_karyawan,))
                    result = cur.fetchone()
                    cur.close()

                    if not result:
                        print "ID karyawan tidak ditemukan. Silakan ketik 'list' untuk menampilkan data semua karyawan."
                        continue

                    data = [
                        ["ID", "NAMA", "JABATAN", "FINGERPRINT ID", "CARD ID", "WAKTU DAFTAR"],
                        [str(result[0]), result[1], result[2], result[3], result[4], result[5]]
                    ]

                    table = AsciiTable(data)
                    print table.table
                    confirm = raw_input("Anda yakin akan menghapus karyawan ini (y/n)?")

                    if confirm == "y" or confirm == "Y":
                        cur = db_con.cursor()
                        cur.execute("DELETE FROM `karyawan` WHERE id = ?", (id_karyawan,))
                        cur.close()
                        db_con.commit()
                        print "Data karyawan berhasil dihapus"
                        # hapus template sidik jari
                        fp.delete(int(result[3]))

                # UNTUK MENJALANKAN PROGRAM GUI
                elif cmd == "run":
                    app = QtGui.QApplication(sys.argv)
                    ui = Main()
                    sys.exit(app.exec_())

                # UNTUK KELUAR DARI PROGRAM
                elif cmd == "exit" or cmd == "quit":
                    print "Bye"
                    exit(0)

                elif cmd == "check memory fp":
                    fp.check_memory()

                elif cmd == "door open":
                    if not GPIO.input(pin_status_pintu):
                        print "Pintu sudah terbuka"
                    else:
                        GPIO.output(pin_buka_pintu, 1)
                        time.sleep(5)
                        GPIO.output(pin_buka_pintu, 0)

                elif cmd == "door status":
                    if GPIO.input(pin_status_pintu):
                        print "Pintu tertutup"
                    else:
                        print "Pintu terbuka"

                elif cmd == "open manual":
                    if not GPIO.input(pin_status_pintu):
                        print "Pintu sudah terbuka"

                    else:
                        print "Tekan tombol"
                        while GPIO.input(pin_buka_manual):
                            pass
                        GPIO.output(pin_buka_pintu, 1)
                        time.sleep(5)
                        GPIO.output(pin_buka_pintu, 0)


                # UNTUK MENAMPILKAN DAFTAR PERINTAR
                elif cmd == "help" or cmd == "?":
                    data = [
                        ['PERINTAH', 'KETERANGAN'],
                        ['?', 'Menampilkan pesan ini'],
                        ['akses', 'Menjalankan program akses pintu CLI'],
                        ['daftar', 'Mendaftarkan karyawan baru'],
                        ['exit', 'Keluar dari progam ini'],
                        ['hapus', 'Menghapus karyawan'],
                        ['clear database', 'Menghapus data karyawan dan log'],
                        ['clear log', 'Menghapus log'],
                        ['check memory fp', 'Check memory sensor finger print'],
                        ['door open', 'Buka pintu'],
                        ['door status', 'Status pintu'],
                        ['open manual', 'Test pintu pake switch'],
                        ['list', 'Daftar semua karyawan'],
                        ['log', 'Menampilkan log akses pintu'],
                        ['run', 'Menjalankan program akses pintu desktop']
                    ]

                    table = AsciiTable(data)
                    print table.table

                # PROGRAM AKSES PINTU (HARUS 2-2NYA)
                elif cmd == "akses":
                    print "Tempelkan jari Anda..."
                    fp_id = fp.scan()

                    if use_nfc:
                        print "Tempelkan kartu Anda..."
                        card_id = nfc.scan()

                    cur = db_con.cursor()

                    if use_nfc:
                        cur.execute("SELECT * FROM `karyawan` WHERE fp_id = ? AND card_id = ?", (fp_id, card_id))
                    else:
                        cur.execute("SELECT * FROM `karyawan` WHERE fp_id = ?", (fp_id,))

                    result = cur.fetchone()
                    cur.close()

                    if result:
                        print "SELAMAT DATANG " + result[1] + ". SILAKAN MASUK."
                        GPIO.output(pin_buka_pintu, 1)
                        terlalu_lama = False
                        start_time = datetime.now()

                        while GPIO.input(pin_status_pintu):
                            if secs(start_time) > 3:
                                terlalu_lama = True
                                break

                        if terlalu_lama:
                            GPIO.output(pin_buka_pintu, 0)
                            print "Anda terlalu lama. Pintu nutup lagi."
                            continue

                        # kunci kembali pintu
                        time.sleep(5)
                        GPIO.output(pin_buka_pintu, 0)
                        cur = db_con.cursor()
                        cur.execute("INSERT INTO `log` (`karyawan_id`) VALUES (?)", (result[0],))
                        cur.close()
                        db_con.commit()

                        while not GPIO.input(pin_status_pintu):
                            print "Mohon tutup pintu"
                            time.sleep(1)

                    else:
                        print "ANDA TIDAK TERDAFTAR"

                elif cmd.strip():
                    print "Perintah tidak dikenal. Ketik '?' untuk bantuan."

                else:
                    pass

            except KeyboardInterrupt:
                print("Bye");
                exit(0)
