# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'new.ui'
#
# Created by: PyQt4 UI code generator 4.11.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName(_fromUtf8("Form"))
        Form.resize(783, 404)
        self.horizontalLayout = QtGui.QHBoxLayout(Form)
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.logo = QtGui.QLabel(Form)
        self.logo.setText(_fromUtf8(""))
        self.logo.setPixmap(QtGui.QPixmap(_fromUtf8("kementan-small.png")))
        self.logo.setAlignment(QtCore.Qt.AlignCenter)
        self.logo.setObjectName(_fromUtf8("logo"))
        self.verticalLayout.addWidget(self.logo, QtCore.Qt.AlignHCenter)
        self.instansi = QtGui.QLabel(Form)
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(False)
        font.setWeight(50)
        self.instansi.setFont(font)
        self.instansi.setAlignment(QtCore.Qt.AlignCenter)
        self.instansi.setObjectName(_fromUtf8("instansi"))
        self.verticalLayout.addWidget(self.instansi, QtCore.Qt.AlignHCenter)
        spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.tanggal = QtGui.QLabel(Form)
        font = QtGui.QFont()
        font.setPointSize(16)
        font.setBold(True)
        font.setWeight(75)
        self.tanggal.setFont(font)
        self.tanggal.setStyleSheet(_fromUtf8("color:blue;"))
        self.tanggal.setAlignment(QtCore.Qt.AlignCenter)
        self.tanggal.setObjectName(_fromUtf8("tanggal"))
        self.verticalLayout.addWidget(self.tanggal, QtCore.Qt.AlignHCenter)
        self.jam = QtGui.QLabel(Form)
        font = QtGui.QFont()
        font.setPointSize(25)
        font.setBold(True)
        font.setWeight(75)
        self.jam.setFont(font)
        self.jam.setStyleSheet(_fromUtf8("color:blue;"))
        self.jam.setAlignment(QtCore.Qt.AlignCenter)
        self.jam.setObjectName(_fromUtf8("jam"))
        self.verticalLayout.addWidget(self.jam, QtCore.Qt.AlignHCenter)
        spacerItem1 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem1)
        self.status_img = QtGui.QLabel(Form)
        self.status_img.setText(_fromUtf8(""))
        self.status_img.setPixmap(QtGui.QPixmap(_fromUtf8("img/scan-80.png")))
        self.status_img.setAlignment(QtCore.Qt.AlignCenter)
        self.status_img.setObjectName(_fromUtf8("status_img"))
        self.verticalLayout.addWidget(self.status_img, QtCore.Qt.AlignHCenter)
        spacerItem2 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem2)
        self.info = QtGui.QLabel(Form)
        font = QtGui.QFont()
        font.setPointSize(14)
        font.setBold(True)
        font.setWeight(75)
        self.info.setFont(font)
        self.info.setAutoFillBackground(False)
        self.info.setStyleSheet(_fromUtf8("color: red;"))
        self.info.setAlignment(QtCore.Qt.AlignCenter)
        self.info.setWordWrap(False)
        self.info.setObjectName(_fromUtf8("info"))
        self.verticalLayout.addWidget(self.info, QtCore.Qt.AlignHCenter)
        self.horizontalLayout.addLayout(self.verticalLayout)
        self.verticalLayout_2 = QtGui.QVBoxLayout()
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.running_text = QtGui.QLabel(Form)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.running_text.setFont(font)
        self.running_text.setStyleSheet(_fromUtf8("color:red"))
        self.running_text.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.running_text.setObjectName(_fromUtf8("running_text"))
        self.verticalLayout_2.addWidget(self.running_text)
        self.videoPlayer = phonon.Phonon.VideoPlayer(Form)
        self.videoPlayer.setObjectName(_fromUtf8("videoPlayer"))
        self.verticalLayout_2.addWidget(self.videoPlayer)
        self.horizontalLayout.addLayout(self.verticalLayout_2)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(_translate("Form", "Form", None))
        self.instansi.setText(_translate("Form", "KEMENTRIAN PERTANIAN", None))
        self.tanggal.setText(_translate("Form", "05 NOV 2017", None))
        self.jam.setText(_translate("Form", "19:41:10", None))
        self.info.setText(_translate("Form", "TEMPELKAN JARI ATAU KARTU ANDA", None))
        self.running_text.setText(_translate("Form", "scrolling text", None))

from PyQt4 import phonon
