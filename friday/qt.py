"""Qt binding adapter supporting PySide6 and the packaged PyQt6 default."""
try:
    from PySide6 import QtCore, QtGui, QtWidgets, QtNetwork
    Signal = QtCore.Signal
    BINDING = "PySide6"
except ModuleNotFoundError:
    from PyQt6 import QtCore, QtGui, QtWidgets, QtNetwork
    Signal = QtCore.pyqtSignal
    BINDING = "PyQt6"

QObject, QTimer, Qt = QtCore.QObject, QtCore.QTimer, QtCore.Qt
QAction, QColor, QIcon = QtGui.QAction, QtGui.QColor, QtGui.QIcon
QKeySequence, QPainter, QPixmap, QShortcut = QtGui.QKeySequence, QtGui.QPainter, QtGui.QPixmap, QtGui.QShortcut
QApplication, QCheckBox, QComboBox = QtWidgets.QApplication, QtWidgets.QCheckBox, QtWidgets.QComboBox
QDialog, QDialogButtonBox, QFileDialog = QtWidgets.QDialog, QtWidgets.QDialogButtonBox, QtWidgets.QFileDialog
QFormLayout, QFrame, QHBoxLayout = QtWidgets.QFormLayout, QtWidgets.QFrame, QtWidgets.QHBoxLayout
QLabel, QLineEdit, QMainWindow, QMenu = QtWidgets.QLabel, QtWidgets.QLineEdit, QtWidgets.QMainWindow, QtWidgets.QMenu
QMessageBox, QPushButton, QScrollArea = QtWidgets.QMessageBox, QtWidgets.QPushButton, QtWidgets.QScrollArea
QSpinBox, QSplitter, QSystemTrayIcon = QtWidgets.QSpinBox, QtWidgets.QSplitter, QtWidgets.QSystemTrayIcon
QTabWidget, QTextBrowser, QTextEdit = QtWidgets.QTabWidget, QtWidgets.QTextBrowser, QtWidgets.QTextEdit
QVBoxLayout, QWidget = QtWidgets.QVBoxLayout, QtWidgets.QWidget
QLocalServer, QLocalSocket = QtNetwork.QLocalServer, QtNetwork.QLocalSocket
