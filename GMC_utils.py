import os,sys, traceback, csv
try: 
    import serial
except ModuleNotFoundError:
    os.system("pip install pyserial")
    import serial
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from functools import partial 
import time
from datetime import datetime

# from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
# from matplotlib.figure import Figure
### Matplot modules needed for plotting

def find_ports() -> list:
    """Finds the serial ports currently open
       and returns them as a list
    """
    import serial.tools.list_ports
    import serial
    ports = serial.tools.list_ports.comports()

    available_ports = [p.name for p in ports]

    return available_ports
class ThreadSignals(QObject):
    '''
    Defines the signals available from a running worker thread
    
    and signals that report count events

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything
        
    '''
    result = pyqtSignal(object)
    finished = pyqtSignal()
    interrupt = pyqtSignal() 
    error = pyqtSignal(tuple)
class CounterSignals(QObject):
    '''
    Defines the signals that report count events

    Supported signals are:

    new_count 
        (the total counts after a period has passed, the period)
        
    count_start
        No data
     
    count_end
        No data
    timer_update
        No data
    '''
    new_count = pyqtSignal(int,int)
    count_start = pyqtSignal()
    count_end = pyqtSignal()
    timer_update = pyqtSignal(int)
class SubThread(QThread):
    """Thread separate for the main thread used to perform multiple actions at once
    """
    def __init__(self, fn,*args,**kwargs):
        super(SubThread, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = ThreadSignals()
        # self.kwargs['count_event']= self.signals.new_count
    def run(self):
        fn_result = None
        try:
            if self.args == () and self.kwargs == {}: #if function has no arguments
                fn_result = self.fn()
            elif self.kwargs == {}: # if function has only positional arguments
                fn_result = self.fn(*self.args)
            elif self.args == (): #if function has only keyword arguments
                fn_result = self.fn(**self.kwargs)
            else: #if the function has both keyword and positional arguments
                fn_result = self.fn(*self.args,**self.kwargs)
        except: #error handling
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
        finally:
            self.signals.finished.emit()
            if fn_result: #emits result to function
                self.signals.result.emit(fn_result)
            self.quit()
class QSelectionDialog(QDialog):
    """Combination of a Dialog Box and a button box
       Similar to SelectionDialog megawidget in Pmw modules
    """
    def __init__(self,title: str, scroll_list: list = [], list_update_function = lambda: None, parent = None):
        super().__init__()
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10,10,10,10)        
        self.scrolledArea = QScrollArea(self)
        self.scrolledArea.setWidgetResizable(True)
        self.scrolledList = QListWidget(self.scrolledArea)
        self.buttonBox = QDialogButtonBox(self)
        self.parent = parent 
        
        self.scrolledArea.setWidget(self.scrolledList)
        self.scrolledList.addItems(scroll_list)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self._add_refresh_button(list_update_function)
        self.buttonBox.setCenterButtons(True)
        
        layout.addWidget(self.scrolledArea)
        layout.addWidget(self.buttonBox)
        self.hide()
        

    def update_list(self,list_items: list):
        """Update list with new items
        """
        self.scrolledList.clear()
        self.scrolledList.addItems(list_items)
    def _add_refresh_button(self,list_generator, args: tuple = ()):   
        """Add a button that can update the list with new items from a function <list_generator>
        """
        refresh_button = QPushButton('Refresh',self.buttonBox)
        refresh_button.clicked.connect(lambda : self.update_list(list_generator()))
        self.buttonBox.addButton(refresh_button,QDialogButtonBox.ActionRole)
class TimedCounter(QGroupBox):  
    """Timed Counter for the GMC Terminal GUI
    """
    def __init__(self, port: serial.Serial, title: str = "Timed Count", parent = None):
        super(TimedCounter, self).__init__()
        self.setTitle(title)
        self.parent = parent
        self.port = port #port corresponding to connected device
        self.t_layout = QGridLayout()
        self.timer_log = [] # list holding dictionaries of the total timed counts
        self.t_signals = CounterSignals() #signals that will notify when a timed count stops or starts
        self.timer_interrupt_flag = False #Flag that can interrupt the count
        
        self._makeTimerText()
        self._makeTimerTable()
        self._makeTimerBox()
        
        self.t_signals.count_start.connect(self.parent.disable_btns) #disables buttons when the count is started
        self.t_signals.count_end.connect(self.parent.enable_btns) #enables buttons when the count is ended
        self.t_signals.new_count.connect(self.update_measurement) #connects new_count signal to slot that will update measurements
        self.t_signals.timer_update.connect(self.update_timer)
        self.setLayout(self.t_layout)
    def _makeTimerText(self):
        """Textbox displaying the data for the timed count
        """
        self.timer_text = QTextEdit(self)
        font_db = QFontDatabase()
        lcd_font_id = font_db.addApplicationFont("fonts/LCD_Solid.ttf")
        lcd_ttf_font = QFont("LCD Solid")
        self.timer_text.setFont(lcd_ttf_font) #set the font for the timer
        self.timer_text.setReadOnly(True)
        self.t_layout.addWidget(self.timer_text,0,0)
        self.default_text_plain = "Elapsed Time:00:00:00\nCount: 0\nAverage CPM: 0.00\nAverage uSv/h: 0.00\nAverage mR/h: 0.00"
        self.timer_text.setPlainText(self.default_text_plain)
        self.timer_text.setStyleSheet("font-size: 22px")
    def _makeTimerTable(self):
        self.timer_table = QTableWidget(6,2,self)
        self.timer_table.setHorizontalHeaderLabels(["Total Counts","Duration (seconds)"])
        self.timer_table.resizeColumnsToContents()
        self.t_layout.addWidget(self.timer_table,0,1)
    def _makeTimerBox(self):
        """Timer holding the the spinboxes and buttons responsible
           for running to timed counts
        """
        self.buttonBox = QGridLayout()
        
        self.buttonBox.addWidget(QLabel('Minutes:',self),0,0) 
        self.minuteBox = QSpinBox(self)
        self.minuteBox.setMaximum(59)
        self.minuteBox.setSuffix(" min")
        self.buttonBox.addWidget(self.minuteBox,0,1)
        
        self.buttonBox.addWidget(QLabel('Seconds:',self),0,2)
        self.secondBox = QSpinBox(self)
        self.secondBox.setMaximum(59)
        self.secondBox.setSuffix(" sec")
        self.buttonBox.addWidget(self.secondBox,0,3)
        
        self.count_run_btn = QPushButton("Run Count",self)
        self.count_run_btn.clicked.connect(lambda : self.run_count(self.minuteBox.value(),self.secondBox.value()))
        self.buttonBox.addWidget(self.count_run_btn,0,4)
        
        self.checkbox = QCheckBox("Logging Counts", self)
        self.buttonBox.addWidget(self.checkbox,1,0,1,2)
        self.checkbox.setChecked(False)
        
        self.clear_last_btn = QPushButton("Clear Last Count",self)
        self.clear_last_btn.clicked.connect(self.clear_last_row)
        self.buttonBox.addWidget(self.clear_last_btn,1,2,1,1)
        
        self.log_clear_btn = QPushButton("Clear Log",self)
        self.log_clear_btn.clicked.connect(self.clear_log)
        self.buttonBox.addWidget(self.log_clear_btn,1,3,1,1)
        
        self.timer_interrupt_btn = QPushButton("Stop Count",self)
        self.timer_interrupt_btn.clicked.connect(self.count_interrupt)
        self.buttonBox.addWidget(self.timer_interrupt_btn,1,4,1,1)
        
        self.t_layout.addLayout(self.buttonBox,1,0,1,2)
       

    def run_count(self,minutes,seconds):
        """Starts running the thread responsible for handling the timed count
        """
        self.timer_text.setPlainText(self.default_text_plain)
        
        self.count_thread = SubThread(self.timed_count,minutes,seconds) 
        self.count_thread.signals.result.connect(self.update_timer_log) #connects result signal to slot
                                                                        #that will upddate the timer log
        self.count_thread.signals.finished.connect(self.t_signals.count_end.emit) # stops the timer when the thread is finished
        if self.port:
            try:
                self.t_signals.count_start.emit()
                self.count_thread.start() #starts thread
            except:
                err_msg = QErrorMessage()
                err_msg.setWindowTitle("Timed Count Error")
                err_msg.showMessage(traceback.format_exc())
    def timed_count(self,minutes,seconds):
        self.port.write(('<HEARTBEAT1>>').encode()) #heartbeat mode on GMC will return total counts every second
        duration = (minutes*60)+seconds
        total_counts = 0
        for t in range(duration): #read in counts every second
            print(self.port)
            try: 
                count = int.from_bytes(self.port.read(4),byteorder="big") 
                total_counts = total_counts+count
                
                if count > 0:
                    self.t_signals.new_count.emit(total_counts,t+1)
                if self.timer_interrupt_flag:
                    self.timer_interrupt_flag = False
                    log = {'total_count': total_counts, 'duration': t}
                    break;
            except serial.serialutil.SerialException:
                err_msg = QErrorMessage()
                err_msg.setWindowTitle("Timed Count Error")
                err_msg.showMessage(traceback.format_exc() + "\nPort was likely disconnected.\nPlease reconnect")
            self.t_signals.timer_update.emit(t+1)
        else:
            log = {'total_count': total_counts, 'duration': duration}
        self.port.write(('<HEARTBEAT0>>').encode())
        return log
    def count_interrupt(self):
        if not self.timer_interrupt_flag:
            self.timer_interrupt_flag = True
    def update_timer(self,cur_time):
        """Updates the timer in the textbox every second
        """
        if not self.timer_interrupt_flag:
            minutes = int((cur_time-(cur_time)%60)/60)
            seconds = cur_time%60 #convert pure second value into minutes and seconds
            print(f'count_time: {cur_time:d}, minutes: {minutes:d}, seconds: {seconds:d}')
            new_elapsed_text = ["Elapsed Time: 00:" +f'{minutes:02}'+":" + f'{seconds:02}']
      
            old_text_measurements = self.timer_text.toPlainText().splitlines()[1:5]
            new_text_lines = new_elapsed_text+old_text_measurements
            new_text  = '\n'.join(new_text_lines)
            self.timer_text.setPlainText(new_text) #changes the text
    def update_measurement(self,total_counts,duration):
        """Updates the measurements in the textbox for every new counts
        """
        if duration < 60:
            average_cpm = total_counts
        else:
            min_duration = duration/60
            average_cpm = total_counts/min_duration #averages out the CPM after 1 minute
        average_usph = average_cpm*0.006
        average_mrph = average_usph*0.1 #unit conversion
        new_text_lines = ['Count: '+str(total_counts),
        'Average CPM: '+f'{average_cpm:.2f}',
        'Average uSv/h: '+f'{average_usph:.2f}',
        'Average mR/h: '+f'{average_mrph:.3f}']
        old_text_elasped = self.timer_text.toPlainText().splitlines()[0]
        new_text_lines.insert(0,old_text_elasped)
        new_text  = '\n'.join(new_text_lines)
        self.timer_text.setPlainText(new_text) #changes the text
    def update_timer_log(self, log: dict):
        if self.checkbox.isChecked():
            self.timer_log.append(log)
            last_row = len(self.timer_log)
            log_count = QTableWidgetItem(str(log['total_count']))
            log_dur  = QTableWidgetItem(str(log['duration']))
            if self.timer_table.rowCount() < last_row:
                self.timer_table.insertRow(last_row-1)
            self.timer_table.setItem(last_row-1,0,log_count)
            self.timer_table.setItem(last_row-1,1,log_dur) #updates the timer log
    def clear_log(self):
        self.timer_table.clearContents()
        self.timer_log=[]
    def clear_last_row(self):
        self.timer_table.setItem(len(self.timer_log)-1,0,QTableWidgetItem(''))
        self.timer_table.setItem(len(self.timer_log)-1,1,QTableWidgetItem(''))
    def closeEvent(self,event): 
        self.port.close()

        # except AttributeError:
            # pass
### Potential Plotting widget; unfinished code
# class CounterPlot(QGroupBox):
    # def __init__(self, port: serial.Serial, title: str = "Count Graph"):
        # super(CounterPlot, self).__init__()
        # self.setTitle(title)
        # self.port = port
        # self.p_layout = QVBoxLayout()
        # self._makePlot()
        # self._makePlotButtons()

        # layout.addWidget(self.button)
        # self.setLayout(self.p_layout)
    # def _makePlot(self):
        # self.figure = Figure()
        # self.canvas = FigureCanvas(self.figure)
        # self.toolbar = NavigationToolbar(self.canvas, self)
        # self.p_layout.addWidget(self.toolbar)
        # self.p_layout.addWidget(self.canvas)
    # def _makePlotButtons(self):
        # self.buttonBox = QGridLayout()
        # self.run_cps_btn = QPushButton("Counts Per Second", self)
        # self.run_cps_btn.clicked.connect(self.run_cps)
        # self.buttonBox.addWidget(self.run_cps_btn,0,0,1,2)
        # self.run_cps_btn = QPushButton("Counts Per Second", self)
        # self.run_cps_btn.clicked.connect(self.run_cps)
        # self.buttonBox.addWidget(self.run_cps_btn,0,0,1,2)
    # def run_cps(self):
        # self.plot_thread = SubThread(self.counts_per_second,minutes,seconds)
        # self.count_thread.signals.result.connect(self.update_timer_log)
        # self.count_thread.signals.new_count.connect(self.update_measurement)
    # def counts_per_second(self):
        
class CounterTerminal(QMainWindow):
    """Main window for GMC Terminal
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle('GMC Terminal')
        self.serialport = None #serial port for device
        self.version = ''
        #self.threadpool = QThreadPool()
        self.setFixedSize(600,400)
        self._createMenubar()
        self._createToolbar()
        self._make_GMC_GUI() #builds the GUI
    def _createMenubar(self):
        self.menu = self.menuBar()
        file_menu = self.menu.addMenu('&File')
        file_menu.addAction('&Exit', self.close)
        file_menu.addAction('Export Count Log',self.export_count_log)
        
        device_menu = self.menu.addMenu('Devices')
        device_menu.addAction('Open Ports',self._make_Portlist)
        device_menu.addAction('Export Configuration Data',self.export_config_data)
        device_menu.addAction('Factory Reset', self.factory_reset)
        device_menu.addAction('Close Ports', self.close_port)
    def _createToolbar(self):
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        self.toolbar.setFixedHeight(30)
        self.toolbar.addWidget(QLabel('Current Device:',self.toolbar))
        self.toolbar.addSeparator()
        self.device_label = QLabel(self.toolbar)
        self.device_label.setStyleSheet("background-color: red; color: black; font-weight: bold")
        self.device_label.setAlignment(Qt.AlignCenter)
        self.device_label.setText('No Device Selected')
        self.device_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.device_label.setLineWidth(2)
        self.device_label.setMidLineWidth(1)
        self.toolbar.addWidget(self.device_label)
        
        self.addToolBarBreak()
        self.volt_toolbar = QToolBar()
        self.addToolBar(self.volt_toolbar)
        self.volt_toolbar.setFixedHeight(30)
        self.volt_toolbar.addSeparator()
        self.volt_toolbar.addWidget(QLabel('Tube 1 Voltage:',self.volt_toolbar))
        self.volt_toolbar.addSeparator()
        self.tube_voltage_reading = QLabel(self.volt_toolbar)
        self.tube_voltage_reading.setStyleSheet("font-weight: bold")
        self.tube_voltage_reading.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.tube_voltage_reading.setLineWidth(3)
        self.tube_voltage_reading.setMidLineWidth(1)
        self.volt_toolbar.addWidget(self.tube_voltage_reading)
        self.volt_toolbar.addSeparator()
        self.volt_write_btn = QPushButton('Write Tube Voltage',self.volt_toolbar)
        self.volt_write_btn.clicked.connect(self._make_Volt_Writer)
        self.volt_toolbar.addWidget(self.volt_write_btn)
        self.volt_toolbar.hide()
        
    def _make_Portlist(self):
        """adds QSelectionDialog widget for opening ports
        
        See GMC_utils.py for details
        """
        self.portlist_dialog = QSelectionDialog('Choose a Port',find_ports(),find_ports)
        open_port_button = self.portlist_dialog.buttonBox.addButton('Open Port',QDialogButtonBox.ActionRole)
        open_port_button.clicked.connect(self.open_ports)
        self.portlist_dialog.show()
    def _make_Volt_Writer(self):
        """Input dialog for changing the tube voltage
        """
        user_percent, okay = QInputDialog().getDouble(self.toolbar, "Choose a voltage percentage for Tube 1",
                                 "Percent (0-100%): ", 50, 0, 100, 1)
        if okay:
            self.write_tube_voltage(user_percent)
    def _make_GMC_GUI(self):
        self.centralwidget = QWidget(self)
        self.GMC_layout = QVBoxLayout(self.centralwidget)
        self._make_Timed_Counter()
        # line_sep = QFrame(self.centralwidget)
        # line_sep.setFrameStyle(QFrame.Raised)
        # line_sep.setFrameShape(QFrame.HLine)
        # line_sep.setLineWidth(1)
        # line_sep.setMidLineWidth(0)
        # self.GMC_layout.addWidget(line_sep)
        ### horizontal separator in case of more widgets below the line
        self.GMC_layout.addStretch(1)
        self.setCentralWidget(self.centralwidget)
        return self.centralwidget
    def _make_Timed_Counter(self):
        """adds TimedCounter widget
        
        See GMC_utils.py for details
        """
        
        timer_layout = QHBoxLayout()
        timer_layout.addStretch(1)
        self.counterBox = TimedCounter(self.serialport,parent = self)
        timer_layout.addWidget(self.counterBox)
        timer_layout.addStretch(1) 
        self.counterBox.move(250,20)
        self.GMC_layout.addLayout(timer_layout)
### Public functions
    def open_ports(self):
    
        portchoice = self.portlist_dialog.scrolledList.currentItem()
        if self.serialport:
            self.close_port()
        try:
            
            self.serialport = serial.Serial(portchoice.text(),115200, timeout = 1) # opens the chosen port
            print(f"Port of choice : {portchoice.text()}")
            self.portlist_dialog.accept() #closes the dialog
            self.serialport.write(('<HEARTBEAT0>>').encode()) # Makes sure heartbeat mode is off; heartbeat may interfere with attempts to read off the device
            time.sleep(0.5)
            self.serialport.write(('<GETVER>>').encode())
            self.version = self.serialport.read(15).decode() #get the device version
            print(self.version)
            if self.version[0:3] == "GMC":
                self.device_label.setText(self.version)
                self.device_label.setStyleSheet("background-color: limegreen; color: black; font-weight: bold")
            else:
                err_msg = QErrorMessage(self)
                err_msg.setWindowTitle("Port Error")
                err_msg.showMessage("Incorrect Device")
                self.close_port()
            if self.version[0:7] == 'GMC-500' or self.version[0:7] == 'GMC-600' : #if the device is a version that supports tube voltage configuration
                print("GMC device with Tube voltage configuration chosen.")
                self.volt_toolbar.show()
                self.read_tube_voltage()
                self.counterBox.port = self.serialport

        except:
            # error dialog
            self.portlist_dialog.reject()
            err_msg = QErrorMessage(self)
            err_msg.setWindowTitle("Port Error")
            err_msg.showMessage(traceback.format_exc())
    def close_port(self):
        if self.serialport:
            self.serialport.close()
            self.volt_toolbar.hide()
            self.serialport = None
            self.device_label.setStyleSheet("background-color: red; color: black; font-weight: bold")
            self.device_label.setText('No Device Selected')
    def read_tube_voltage(self)->float:
        """Reads the tube voltage of tube 1
        """
        
        if self.serialport:
            try:
                self.serialport.write(('<GETCFG>>').encode())
                cfg = self.serialport.read(512) #read in the CFG
                print(cfg)
                volt_percent = cfg[330]*(2/3) #get the voltage "percent" and convert it from out of 150 to out of 100
                tube_volt_text = f"{volt_percent:.2f}"+"%"
                self.tube_voltage_reading.setText(tube_volt_text)
            except:
                err_msg = QErrorMessage(self)
                err_msg.setWindowTitle("Voltage Read Error")
                err_msg.showMessage(traceback.format_exc())
    def write_tube_voltage(self,voltage_percent: float):
        """Writes a given voltage percentage to a GQ GMC
        """
        if self.serialport: #if the port is open
            try:
                #self.volt_read_btn.setEnabled(False)
                self.volt_write_btn.setEnabled(False)
                
                num_to_bytes = partial(int.to_bytes,byteorder = 'big')
                
                byte_percent = num_to_bytes(round(voltage_percent*(0.01)*150),1)
                #converts the percentage into an integer /150, then to a bytes object
                
                self.serialport.write(('<GETCFG>>').encode())
                cfg = bytearray(self.serialport.read(512)) #get the current configuration

                self.serialport.write(('<ECFG>>').encode())
                confirmation = self.serialport.read(1)
                if confirmation != b'\xAA':
                    print("Erasure failed:  " + confirmation.hex().upper()) #erase the current configuration
         
                cfg[330:331] = byte_percent #modify the config with the new percentage
                for address in range(512): #re-write configuration data with new data
                    write_package = ('<WCFG').encode() + num_to_bytes(address,2) + num_to_bytes(cfg[address],1) + ('>>').encode()
                    self.serialport.write(write_package)
                    write_confirmation = self.serialport.read(1)
                    if write_confirmation != b'\xAA':
                        print(write_package)
                        print("Write Failed: " + write_confirmation.hex().upper()+ f" index: {address:d}")
                
                self.serialport.write(('<CFGUPDATE>>').encode())
                confirmation = self.serialport.read(1)
                if confirmation != b'\xAA':
                    print("Update failed: " + confirmation.hex().upper()) #update the device
                self.volt_write_btn.setEnabled(True)
                self.read_tube_voltage()
            except serial.serialutil.SerialException:
                err_msg = QErrorMessage(self)
                err_msg.setWindowTitle("Voltage Read Error")
                err_msg.showMessage(traceback.format_exc())
                self.volt_write_btn.setEnabled(True)
                self.close_port()
            except:
                err_msg = QErrorMessage(self)
                err_msg.setWindowTitle("Voltage Read Error")
                err_msg.showMessage(traceback.format_exc())
                self.volt_write_btn.setEnabled(True)
    def enable_btns(self):
        #self.volt_read_btn.setEnabled(True)
        self.volt_write_btn.setEnabled(True)        
        self.counterBox.count_run_btn.setEnabled(True)
    def disable_btns(self):
        #self.volt_read_btn.setEnabled(False)
        self.volt_write_btn.setEnabled(False)
        self.counterBox.count_run_btn.setEnabled(False)
    def export_config_data(self):
        """Exports the configuration data to a text file
        """
        if self.serialport:
            try:
                self.serialport.write(('<GETCFG>>').encode())
                cfg = self.serialport.read(512)
                filename = QFileDialog.getSaveFileName(self, 'Save config', 
                    'config_files',"Text Files (*.txt *.csv)")
                with open(filename[0],'w') as config_file:
                    config_file.write("Configuration data from " + self.version + "\n")
                    for address in range(len(cfg)):
                        if cfg[address] >= 32 and cfg[address] <= 126:
                            char = chr(cfg[address]) + ' '
                        else: 
                            char = f'{cfg[address]:0>2X}' + ' '
                        config_file.write(char)
                        if address%32 == 0 and address != 0:
                            config_file.write('\n')
            except:
                err_msg = QErrorMessage(self)
                err_msg.setWindowTitle("Port Error")
                err_msg.showMessage(traceback.format_exc())
    def export_count_log(self):
        """Exports the count log data
        """
        #filename = "logs\\" + datetime.now().strftime("%Y-%m-%d-%H%M%S") + "-data.csv"
        filename = QFileDialog.getSaveFileName(self, 'Save config', 
                'logs',"Text Files (*.txt *.csv)")
        with open(filename[0],'w',newline='') as f:
            fieldnames = ['#','Total Counts','Duration (seconds)']
            wr = csv.writer(f)
            wr.writerows([fieldnames])
            n = 1
            for log in self.counterBox.timer_log:
                wr.writerow([n,log['total_count'],log['duration']])   
                n = n + 1
    def factory_reset(self):
        """Resets device to factory default.
        Useful for debugging.
        """
        if self.serialport:
            try:  
                self.serialport.write(('<FACTORYRESET>>').encode())
                confirmation = self.serialport.read(1)
            except:
                err_msg = QErrorMessage(self)
                err_msg.setWindowTitle("Port Error")
                err_msg.showMessage(traceback.format_exc())
    def closeEvent(self,event):
        if self.serialport:
            self.serialport.write(('<HEARTBEAT0>>').encode())
            self.serialport.close()
def main():
    app = QApplication(sys.argv) 
    port = serial.Serial('COM6',115200)
    win = QSelectionDialog('title')

    win.show()

    
    sys.exit(app.exec_())
if __name__ == '__main__':
    main()