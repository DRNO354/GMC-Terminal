import sys, traceback
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


from GMC_utils import CounterSignals, SubThread, TimedCounter, QSelectionDialog, CounterTerminal


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('img/UMD_Radiation.png'))
    win = CounterTerminal()

    win.show()
    
    sys.exit(app.exec_())
if __name__ == '__main__':
    main()