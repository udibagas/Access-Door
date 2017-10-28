# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'main.ui'
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
        Form.resize(886, 521)
        self.horizontalLayout = QtGui.QHBoxLayout(Form)
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.verticalLayout_2 = QtGui.QVBoxLayout()
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout_2.addItem(spacerItem)
        self.logo = QtGui.QLabel(Form)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.logo.sizePolicy().hasHeightForWidth())
        self.logo.setSizePolicy(sizePolicy)
        self.logo.setText(_fromUtf8(""))
        self.logo.setPixmap(QtGui.QPixmap(_fromUtf8("logo.png")))
        self.logo.setAlignment(QtCore.Qt.AlignCenter)
        self.logo.setObjectName(_fromUtf8("logo"))
        self.verticalLayout_2.addWidget(self.logo)
        spacerItem1 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout_2.addItem(spacerItem1)
        self.instansi = QtGui.QLabel(Form)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        font.setWeight(75)
        self.instansi.setFont(font)
        self.instansi.setStyleSheet(_fromUtf8(""))
        self.instansi.setAlignment(QtCore.Qt.AlignCenter)
        self.instansi.setWordWrap(True)
        self.instansi.setObjectName(_fromUtf8("instansi"))
        self.verticalLayout_2.addWidget(self.instansi)
        spacerItem2 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout_2.addItem(spacerItem2)
        self.horizontalLayout.addLayout(self.verticalLayout_2)
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        spacerItem3 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem3)
        self.tanggal = QtGui.QLabel(Form)
        font = QtGui.QFont()
        font.setPointSize(20)
        font.setBold(True)
        font.setWeight(75)
        self.tanggal.setFont(font)
        self.tanggal.setStyleSheet(_fromUtf8("color:blue"))
        self.tanggal.setAlignment(QtCore.Qt.AlignCenter)
        self.tanggal.setObjectName(_fromUtf8("tanggal"))
        self.verticalLayout.addWidget(self.tanggal)
        self.jam = QtGui.QLabel(Form)
        font = QtGui.QFont()
        font.setPointSize(34)
        font.setBold(True)
        font.setWeight(75)
        self.jam.setFont(font)
        self.jam.setStyleSheet(_fromUtf8("color:blue"))
        self.jam.setAlignment(QtCore.Qt.AlignCenter)
        self.jam.setObjectName(_fromUtf8("jam"))
        self.verticalLayout.addWidget(self.jam)
        spacerItem4 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem4)
        self.fp_image = QtGui.QLabel(Form)
        self.fp_image.setText(_fromUtf8(""))
        self.fp_image.setObjectName(_fromUtf8("fp_image"))
        self.verticalLayout.addWidget(self.fp_image)
        spacerItem5 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem5)
        self.info = QtGui.QLabel(Form)
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.info.setFont(font)
        self.info.setStyleSheet(_fromUtf8("color:red"))
        self.info.setAlignment(QtCore.Qt.AlignCenter)
        self.info.setWordWrap(True)
        self.info.setObjectName(_fromUtf8("info"))
        self.verticalLayout.addWidget(self.info)
        spacerItem6 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem6)
        self.horizontalLayout.addLayout(self.verticalLayout)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(_translate("Form", "Form", None))
        self.instansi.setText(_translate("Form", "", None))
        self.tanggal.setText(_translate("Form", "tanggal", None))
        self.jam.setText(_translate("Form", "jam", None))
        self.info.setText(_translate("Form", "info", None))
