import sip
import sys
sip.setapi('QVariant', 2)
from PyQt4.QtGui import QApplication
from outage_browser import MainWindow
import platform

if platform.system() == "Windows":

    print "Running on Windows"
    app = QApplication(sys.argv)
    print "ready to call MainWindow"
    window = MainWindow(app=app)
    print "showing main window"
    window.show()
    #window.exec_()
    while app.exec_():
        pass
    print "Exiting from Windows"
    sys.exit()
else:
    print "Unknown system - run this on windows"
