import sys
import os
import serial
import serial.tools.list_ports
import datetime
from collections import deque
from PySide6.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox, QMdiSubWindow
from PySide6.QtCore import QThread, Signal, QObject, QDateTime
import pyqtgraph as pg

# --- FIX PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# --- DINAMIS IMPORT ---
try:
    import dashboard_ui
    ui_class_name = [name for name in dir(dashboard_ui) if name.startswith('Ui_')][0]
    UI_CLASS = getattr(dashboard_ui, ui_class_name)
    print(f"Berhasil memuat UI Class: {ui_class_name}")
except Exception as e:
    print(f"Gagal memuat UI: {e}")
    sys.exit()

class SerialWorker(QObject):
    data_received = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, port):
        super().__init__()
        self.port = port
        self.running = True

    def run(self):
        try:
            ser = serial.Serial(self.port, 115200, timeout=0.01)
            ser.flushInput()
            while self.running:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        values = line.split(',')
                        if len(values) == 8:
                            self.data_received.emit(values)
                QThread.msleep(1)
            ser.close()
        except Exception as e:
            self.error_occurred.emit(str(e))

class DroidDAQ(QMainWindow):
    def __init__(self, ui_layout):
        super().__init__()
        self.ui = ui_layout
        self.ui.setupUi(self)

        self.is_recording = False
        self.update_counter = 0
        self.colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", 
                       "#FF00FF", "#00FFFF", "#FFA500", "#FFFFFF"]
        
        self.data_storage = [deque(maxlen=200) for _ in range(8)]
        
        self.init_ui()
        self.setup_mdi_graphs()
        self.setup_signals()

    def init_ui(self):
        # Set path default
        self.ui.lineEdit_TestFolder.setText(current_dir)
        
        # Mapping Widget (Gunakan pengecekan hasattr agar tidak crash jika nama di Designer beda)
        self.ch_lcds = [getattr(self.ui, f"lcdNumber_Ch{i}", None) for i in range(1, 9)]
        self.ch_checkboxes = [getattr(self.ui, f"checkBox_Ch{i}", None) for i in range(1, 9)]
        self.ch_labels = [getattr(self.ui, f"label_NameCh{i}", None) for i in range(1, 9)]

    def setup_mdi_graphs(self):
        """Memasukkan grafik ke dalam mdiArea"""
        if not hasattr(self.ui, 'mdiArea'):
            print("Peringatan: mdiArea tidak ditemukan, grafik mungkin tidak tampil.")
            return

        self.plot_widget = pg.PlotWidget(title="DroidDAQ Real-time Monitor")
        self.plot_widget.setBackground('k')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()

        self.curves = []
        for i in range(8):
            curve = self.plot_widget.plot(pen=pg.mkPen(self.colors[i], width=1.5), name=f"Ch{i+1}")
            self.curves.append(curve)
            # Warnai label jika widgetnya ada
            if self.ch_labels[i]:
                self.ch_labels[i].setStyleSheet(f"background-color: {self.colors[i]}; color: black; font-weight: bold;")

        # Tambahkan ke MDI
        sub = QMdiSubWindow()
        sub.setWidget(self.plot_widget)
        sub.setWindowTitle("Graphical Visualization")
        self.ui.mdiArea.addSubWindow(sub)
        sub.show()
        self.ui.mdiArea.tileSubWindows()

    def setup_signals(self):
        # Menghubungkan tombol dengan fungsi (Sudah diperbaiki ke pushButton_TestBrowse)
        self.ui.pushButton_Scan.clicked.connect(self.scan_ports)
        self.ui.pushButton_Connect.clicked.connect(self.toggle_connection)
        self.ui.pushButton_StartRecord.clicked.connect(self.toggle_record)
        
        # FIX NAMA: pushButton_TestBrowse
        if hasattr(self.ui, 'pushButton_TestBrowse'):
            self.ui.pushButton_TestBrowse.clicked.connect(self.select_folder)
        elif hasattr(self.ui, 'pushButton_TestBrowser'):
            self.ui.pushButton_TestBrowser.clicked.connect(self.select_folder)

    def scan_ports(self):
        self.ui.comboBox_ComPort.clear()
        self.ui.comboBox_ComPort.addItems([p.device for p in serial.tools.list_ports.comports()])

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Penyimpanan")
        if folder:
            self.ui.lineEdit_TestFolder.setText(folder)

    def toggle_connection(self):
        if self.ui.pushButton_Connect.text() == "Connect":
            port = self.ui.comboBox_ComPort.currentText()
            if not port: return
            
            self.thread = QThread()
            self.worker = SerialWorker(port)
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.data_received.connect(self.handle_data)
            self.worker.error_occurred.connect(self.on_error)
            self.thread.start()
            self.ui.pushButton_Connect.setText("Disconnect")
        else:
            self.stop_serial()

    def stop_serial(self):
        if hasattr(self, 'worker'):
            self.worker.running = False
            self.thread.quit()
            self.thread.wait()
        self.ui.pushButton_Connect.setText("Connect")

    def handle_data(self, vals):
        try:
            f_vals = [float(v) for v in vals]
            
            # Record ke file
            if self.is_recording:
                ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                with open(self.filename, 'a') as f:
                    f.write(f"{ts}," + ",".join(vals) + "\n")

            # Update UI secara periodik
            self.update_counter += 1
            if self.update_counter >= 5:
                for i in range(8):
                    if self.ch_lcds[i]: self.ch_lcds[i].display(f_vals[i])
                    
                    if self.ch_checkboxes[i] and self.ch_checkboxes[i].isChecked():
                        self.data_storage[i].append(f_vals[i])
                        self.curves[i].setData(list(self.data_storage[i]))
                        self.curves[i].show()
                    else:
                        self.curves[i].hide()
                
                if self.is_recording: self.update_progress()
                self.update_counter = 0
        except: pass

    def toggle_record(self):
        if not self.is_recording:
            folder = self.ui.lineEdit_TestFolder.text()
            if not os.path.exists(folder): os.makedirs(folder)
            
            name = self.ui.lineEdit_TestName.text() or "Data"
            ts = datetime.datetime.now().strftime("%y%m%d%H%M%S")
            self.filename = os.path.join(folder, f"{name}_{ts}.csv")
            
            with open(self.filename, 'w') as f:
                f.write("Time,Ch1,Ch2,Ch3,Ch4,Ch5,Ch6,Ch7,Ch8\n")
            
            self.rec_start = QDateTime.currentDateTime()
            self.is_recording = True
            self.ui.pushButton_StartRecord.setText("Stop Record")
        else:
            self.is_recording = False
            self.ui.pushButton_StartRecord.setText("Start Record")
            self.ui.progressBar.setValue(0)

    def update_progress(self):
        d_text = self.ui.lineEdit_TestDuration.text()
        if d_text.isdigit():
            limit = int(d_text)
            elapsed = self.rec_start.secsTo(QDateTime.currentDateTime())
            self.ui.progressBar.setValue(min(int((elapsed/limit)*100), 100))
            if elapsed >= limit: self.toggle_record()

    def on_error(self, err):
        self.stop_serial()
        QMessageBox.critical(self, "Error", err)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DroidDAQ(UI_CLASS())
    window.show()
    sys.exit(app.exec())