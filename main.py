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

class Main(QtGui.QWidget, main_ui.Ui_Form):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)

        self.update_clock()
        self.update_info("TEMPELKAN JARI ANDA...")
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
        global db_con
        global fp
        global nfc

    def __del__(self):
        self.exiting = True
        self.wait()

    def secs(self, start_time):
        dt = datetime.now() - start_time
        return dt.seconds

    def read_card(self):
        start_time = datetime.now()

        while not self.exiting:
            if self.secs(start_time) > 10:
                self.emit(QtCore.SIGNAL('updateInfo'), "WAKTU HABIS")
                time.sleep(2)
                return False

            uid = nfc.pn532.read_passive_target()
            if uid is "no_card":
                continue

            return str(binascii.hexlify(uid))

    def run(self):
        time.sleep(2)
        while not self.exiting:
            self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN JARI ANDA...")

            while not fp.fp.readImage():
                pass

            fp.fp.convertImage(0x01)
            result = fp.fp.searchTemplate()
            fp_id = result[0]

            if fp_id == -1:
                self.emit(QtCore.SIGNAL('updateInfo'), "SIDIK JARI TIDAK DITEMUKAN!")
                time.sleep(2)
                continue

            self.emit(QtCore.SIGNAL('updateInfo'), "TEMPELKAN KARTU...")
            card_id = self.read_card()

            if card_id:
                cur = db_con.cursor()
                cur.execute("SELECT * FROM karyawan WHERE `fp_id` = ? AND `card_id` = ?", (fp_id, card_id))
                result = cur.fetchone()
                cur.close()

                if not result:
                    self.emit(QtCore.SIGNAL('updateInfo'), "SIDIK JARI DAN KARTU TIDAK COCOK")
                    time.sleep(2)
                    continue

                self.emit(QtCore.SIGNAL('updateInfo'), "SILAKAN MASUK, " + result[1].upper())

                cur = db_con.cursor()
                cur.execute("INSERT INTO `log` (`karyawan_id`) VALUES (?)", (result[0],))
                cur.close()
                db_con.commit()

                # buka kunci pintu selama 3 detik
                GPIO.output(buka_pintu, 1)
                time.sleep(10)
                # kunci kembali pintu
                GPIO.output(buka_pintu, 0)


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
            pass

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

    def enroll(self):
        ## Informasi fingerprint
        print('Template terpakai saat ini: ' + str(self.fp.getTemplateCount()) + '/' + str(self.fp.getStorageCapacity()))
        ## Enroll jari
        print('Tempelkan jari Anda...')

        while not self.fp.readImage():
            pass

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
                pass

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


if __name__ == "__main__":
    # db_con = MySQLdb.connect(host="localhost", user="root", passwd="bismillah", db="access_door")
    db_con = sqlite3.connect("access_door.db", check_same_thread = False)

    # populate db
    db_con.execute("CREATE TABLE IF NOT EXISTS `karyawan` ( \
        `id` INTEGER PRIMARY KEY AUTOINCREMENT, \
        `nama` varchar(30) NOT NULL, \
        `jabatan` varchar(30) NOT NULL, \
        `card_id` varchar(20) NOT NULL, \
        `fp_id` varchar(20) NOT NULL, \
        `waktu_daftar` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)");

    db_con.execute("CREATE TABLE IF NOT EXISTS `log` ( \
        `id` INTEGER PRIMARY KEY AUTOINCREMENT, \
        `karyawan_id` int(11) NOT NULL, \
        `waktu` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    nfc = NFC("/dev/serial2")
    fp = FP("/dev/serial1")

    # PIN pada raspberry
    buka_pintu = 37  # untuk trigger buka pintu

    # inisiasi GPIO pada raspberry
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(buka_pintu, GPIO.OUT)

    if len(sys.argv) > 1 and sys.argv[1] == "run":
        app = QtGui.QApplication(sys.argv)
        ui = Main()
        sys.exit(app.exec_())

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
                cur.execute("INSERT INTO `karyawan` (`nama`, `jabatan`, `card_id`, `fp_id`) VALUES (?, ?, ?, ?)", (nama, jabatan, card_id, fp_id))
                cur.close()
                db_con.commit()

                print "Pendaftaran BERHASIL!"

            # UNTUK MELIHAT DAFTAR SEMUA KARYAWAN
            elif cmd == "list":
                cur = db_con.cursor()
                cur.execute("SELECT * FROM `karyawan` ORDER BY `nama` ASC")
                result = cur.fetchall()
                cur.close()

                data = [["ID", "NAMA", "JABATAN", "CARD ID", "FINGERPRINT ID", "WAKTU DAFTAR"]]

                for row, item in enumerate(result):
                    data.append([str(item[0]), item[1], item[2], item[3], item[4], item[5]])

                table = AsciiTable(data)
                print table.table

            # UNTUK MELIHAT LOG KARYAWAN MASUK
            elif cmd == "log":
                cur = db_con.cursor()
                cur.execute("SELECT `log`.`waktu`, `karyawan`.`nama`, `karyawan`.`jabatan` FROM `log` LEFT JOIN `karyawan` ON `karyawan`.`id` = `log`.`karyawan_id` ORDER BY `log`.`waktu` ASC")
                result = cur.fetchall()
                cur.close()

                data = [["WAKTU MASUK", "NAMA", "JABATAN"]]

                for row, item in enumerate(result):
                    data.append([str(item[0]), item[1], item[2]])

                table = AsciiTable(data)
                print table.table

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
                    ["ID", "NAMA", "JABATAN", "CARD ID", "FINGERPRINT ID", "WAKTU DAFTAR"],
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
                    fp.delete(int(result[4]))

            # UNTUK MENJALANKAN PROGRAM GUI
            elif cmd == "run":
                app = QtGui.QApplication(sys.argv)
                ui = Main()
                sys.exit(app.exec_())

            # UNTUK KELUAR DARI PROGRAM
            elif cmd == "exit" or cmd == "quit":
                print "Bye"
                exit(0)

            # UNTUK MENAMPILKAN DAFTAR PERINTAR
            elif cmd == "help" or cmd == "?":
                data = [
                    ['PERINTAH', 'KETERANGAN'],
                    ['?', 'Menampilkan pesan ini'],
                    ['akses', 'Menjalankan program akses pintu CLI'],
                    ['daftar', 'Mendaftarkan karyawan baru'],
                    ['exit', 'Keluar dari progam ini'],
                    ['hapus', 'Menghapus karyawan'],
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
                print "Tempelkan kartu Anda..."
                card_id = nfc.scan()

                cur = db_con.cursor()
                cur.execute("SELECT * FROM `karyawan` WHERE fp_id = ? AND card_id = ?", (fp_id, card_id))
                result = cur.fetchone()
                cur.close()

                if result:
                    print "SELAMAT DATANG " + result[1] + ". SILAKAN MASUK."
                    cur = db_con.cursor()
                    cur.execute("INSERT INTO `log` (`karyawan_id`) VALUES (?)", (result[0],))
                    cur.close()
                    db_con.commit()

                    # buka kunci pintu selama 3 detik
                    GPIO.output(buka_pintu, 1)
                    time.sleep(10)
                    # kunci kembali pintu
                    GPIO.output(buka_pintu, 0)

                else:
                    print "ANDA TIDAK TERDAFTAR"

            elif cmd.strip():
                print "Perintah tidak dikenal. Ketik '?' untuk bantuan."

            else:
                pass

        except KeyboardInterrupt:
            print("Bye");
            exit(0)
