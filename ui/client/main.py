import sys

from PySide6.QtWidgets import *

from PySide6.QtCore import Qt, Signal, Slot, QFile, QTextStream

import os

from ui.widgets.DashboardCard import DashboardCard
from ui.widgets.Sidebar import Sidebar

if os.getenv("DEV_MODE") == 0:
    import resources_rc


def create_management_tab():
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(30, 30, 30, 30)
    layout.setSpacing(20)

    # Stats Row
    stats_layout = QHBoxLayout()
    stats_layout.addWidget(DashboardCard("Local Training Round", "Round 14", "Accuracy: 84.1%", "#0d9488"))
    stats_layout.addWidget(DashboardCard("Resource Status", "Optimized", "GPU Acceleration Active", "#3b82f6"))
    stats_layout.addWidget(DashboardCard("Data Quality Alert", "3% Outliers", "View Quality Report", "#f43f5e"))
    layout.addLayout(stats_layout)

    # Config Form Card
    form_card = QFrame()
    form_card.setObjectName("GlassCard")
    form_card.setProperty("class", "GlassCard")
    form_layout = QHBoxLayout(form_card)

    for label_text, default_val in [("Local Epochs", "3"), ("Batch Size", "32"), ("LR", "0.001")]:
        v_box = QVBoxLayout()
        v_box.addWidget(QLabel(label_text.upper()))
        edit = QLineEdit(default_val)
        edit.setStyleSheet("padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px;")
        v_box.addWidget(edit)
        form_layout.addLayout(v_box)

    layout.addWidget(form_card)

    # Action Buttons
    sync_btn = QPushButton("MANUALLY SYNCHRONIZE WEIGHTS")
    sync_btn.setProperty("class", "PrimaryButton")
    layout.addWidget(sync_btn)

    layout.addStretch()
    return page


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

        # Add Tabs
        self.content_stack.addWidget(create_management_tab())
        self.content_stack.addWidget(QLabel("Inference Tab (Placeholder)"))
        self.content_stack.addWidget(QLabel("Insights Tab (Placeholder)"))

        # Sidebar
        self.sidebar = Sidebar(self.content_stack)

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
