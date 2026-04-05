import sys
import os

from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QFile, QTextStream, QThread

from ui.widgets.ConfigurationTab import ConfigurationTab
from ui.widgets.InferenceTab import InferenceTab
from ui.widgets.InsightsTab import InsightsTab
from ui.widgets.Sidebar import Sidebar

# Import the controller we just created
from ui.client.controller import FLWorker

if os.getenv("DEV_MODE") == "0":
    import resources_rc


class ClientUi(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MedLink FL Dashboard")
        self.resize(1100, 700)
        self.load_resources()

        # Initialize background worker and thread
        self.worker_thread = QThread()
        self.fl_worker = FLWorker()
        self.fl_worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        # Central Widget & Main Horizontal Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content Stack
        self.content_stack = QStackedWidget()

        self.config_tab = ConfigurationTab()
        self.inference_tab = InferenceTab()
        self.insights_tab = InsightsTab()

        # Wire up Controller to the Tabs
        # 1. Configuration Tab (Sync + Real-time Training Status)
        self.config_tab.sync_requested.connect(self.fl_worker.start_fl_client)
        self.fl_worker.training_started.connect(self.config_tab.on_training_started)
        self.fl_worker.training_ended.connect(self.config_tab.on_training_ended)
        self.fl_worker.fl_client_stopped.connect(self.config_tab.on_fl_client_stopped)
        self.fl_worker.log_message.connect(self.config_tab.append_log)
        
        # 2. Inference Tab (Prediction via background model)
        self.inference_tab.predict_requested.connect(self.fl_worker.run_prediction)
        self.fl_worker.prediction_result.connect(self.inference_tab.display_prediction_result)

        # Add Tabs
        self.content_stack.addWidget(self.config_tab)
        self.content_stack.addWidget(self.inference_tab)
        self.content_stack.addWidget(self.insights_tab)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.nav_clicked.connect(self.content_stack.setCurrentIndex)

        # Main Content Area (Topbar + Stack)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)

        topbar = QFrame()
        topbar.setObjectName("Topbar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.addWidget(QLabel("Node Configuration"))
        topbar_layout.addStretch()
        topbar_layout.addWidget(QLabel(f"NODE_{os.environ.get('CLIENT_ID', 'DEFAULT')}"))

        right_layout.addWidget(topbar)
        right_layout.addWidget(self.content_stack)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(right_container)

        main_layout.setStretch(0, 1)
        main_layout.setStretch(1, 4)

    def load_resources(self):
        # This gets the directory where main.py actually lives
        base_dir = os.path.dirname(os.path.abspath(__file__))

        if os.getenv("DEV_MODE") == "0":  # Env vars are always strings!
            file = QFile(":/ui/assets/style.qss")
            if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
                self.setStyleSheet(QTextStream(file).readAll())
        else:
            # Join the base_dir with the assets folder
            qss_path = os.path.join(base_dir, "assets", "style.qss")
            try:
                with open(qss_path, "r") as file:
                    self.setStyleSheet(file.read())
                    print(f"Loaded QSS from: {qss_path}")
            except FileNotFoundError:
                print(f"❌ Error: Still can't find {qss_path}")

    def closeEvent(self, event):
        # Cleanup thread gracefully when window closes
        self.worker_thread.quit()
        self.worker_thread.wait()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClientUi()
    window.show()
    sys.exit(app.exec())
