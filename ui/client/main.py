import sys

from PySide6.QtWidgets import *

from PySide6.QtCore import Qt, Signal, Slot, QFile, QTextStream

import os

from ui.widgets.ConfigurationTab import ConfigurationTab
from ui.widgets.InferenceTab import InferenceTab
from ui.widgets.InsightsTab import InsightsTab
from ui.widgets.Sidebar import Sidebar

if os.getenv("DEV_MODE") == "0":
    import resources_rc




class ClientUi(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MedLink FL Dashboard")
        self.resize(1100, 700)
        self.load_resources()

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
        topbar_layout.addWidget(QLabel("NODE_HOSP_001"))

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







if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClientUi()
    window.show()
    sys.exit(app.exec())
