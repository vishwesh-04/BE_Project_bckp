import sys
import os

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QFrame, QLabel, QCheckBox
)
from PySide6.QtCore import Qt, QFile, QTextStream, QThread, Slot, QSettings

# ── Tab widgets ──────────────────────────────────────────────────────────────
from ui.widgets.DashboardTab import DashboardTab
from ui.widgets.ConfigurationTab import ConfigurationTab
from ui.widgets.InferenceTab import InferenceTab
from ui.widgets.InsightsTab import InsightsTab
from ui.widgets.HistoryTab import HistoryTab
from ui.widgets.Sidebar import Sidebar

# ── Controller ───────────────────────────────────────────────────────────────
from ui.client.controller import FLWorker

if os.getenv("DEV_MODE") == "0":
    import resources_rc


# ── Tab index constants (must match Sidebar.NAV_ITEMS order) ─────────────────
TAB_DASHBOARD  = 0
TAB_INFERENCE  = 1
TAB_INSIGHTS   = 2
TAB_HISTORY    = 3
TAB_SETTINGS   = 4

TAB_TITLES = {
    TAB_DASHBOARD: "Node Dashboard",
    TAB_INFERENCE: "Live Clinical Prediction",
    TAB_INSIGHTS:  "SHAP Interpretability Dashboard",
    TAB_HISTORY:   "Federated Round History",
    TAB_SETTINGS:  "Node Settings",
}


class ClientUi(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MedLink FL Pro — Clinical Node Dashboard")
        self.resize(1280, 750)
        self.load_resources()

        # Initialize QSettings
        self.settings = QSettings("MedLink", "FLNodeDashboard")

        # Load or set default node settings
        self.server_address = self.settings.value("server_address", "127.0.0.1:45678")
        self.local_epochs = int(self.settings.value("local_epochs", 3))
        self.batch_size = int(self.settings.value("batch_size", 32))
        self.learning_rate = float(self.settings.value("learning_rate", 0.001))

        # ── Background worker ─────────────────────────────────────────────
        self.worker_thread = QThread()
        self.fl_worker = FLWorker()
        self.fl_worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        # ── Central widget ────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Content stack (5 tabs) ────────────────────────────────────────
        self.content_stack = QStackedWidget()

        self.dashboard_tab  = DashboardTab()
        self.inference_tab  = InferenceTab()
        self.insights_tab   = InsightsTab()
        self.history_tab    = HistoryTab()
        self.config_tab     = ConfigurationTab()   # Settings / Node Config

        self.content_stack.addWidget(self.dashboard_tab)   # 0
        self.content_stack.addWidget(self.inference_tab)   # 1
        self.content_stack.addWidget(self.insights_tab)    # 2
        self.content_stack.addWidget(self.history_tab)     # 3
        self.content_stack.addWidget(self.config_tab)      # 4

        # Initialize UI elements with settings
        self.config_tab.server_input.setText(self.server_address)
        self.config_tab.epochs_input.setText(str(self.local_epochs))
        self.config_tab.batch_input.setText(str(self.batch_size))
        self.config_tab.lr_input.setText(str(self.learning_rate))

        # ── Sidebar ───────────────────────────────────────────────────────
        self.sidebar = Sidebar()
        self.sidebar.nav_clicked.connect(self._on_tab_changed)

        # ── Right side: topbar + content ──────────────────────────────────
        right_container = QWidget()
        right_container.setObjectName("RightContainer")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_layout.addWidget(self._build_topbar())
        right_layout.addWidget(self.content_stack)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(right_container)
        main_layout.setStretch(0, 0)   # sidebar: fixed natural width
        main_layout.setStretch(1, 1)   # content: expands

        # ── Wire FL worker → tabs ─────────────────────────────────────────
        self.config_tab.sync_requested.connect(self._on_sync_requested)
        self.fl_worker.training_started.connect(self.config_tab.on_training_started)
        self.fl_worker.training_ended.connect(self.config_tab.on_training_ended)
        self.fl_worker.fl_client_started.connect(self.config_tab.on_fl_client_started)
        self.fl_worker.fl_client_stopped.connect(self.config_tab.on_fl_client_stopped)
        self.fl_worker.mute_rejected.connect(self.on_mute_rejected)
        self.fl_worker.log_message.connect(self.config_tab.append_log)

        self.inference_tab.predict_requested.connect(self.fl_worker.run_prediction)
        self.fl_worker.prediction_result.connect(self.inference_tab.display_prediction_result)

        # Dashboard "Edit Configuration" button → jump to settings tab
        self.dashboard_tab.goto_settings_requested.connect(
            lambda: self._on_tab_changed(TAB_SETTINGS)
        )
        self.dashboard_tab.open_logs_requested.connect(self.config_tab.show_logs)

        # History tab "View Logs" button → open logs dialog
        self.history_tab.open_logs_requested.connect(
            lambda _round: self.config_tab.show_logs()
        )

        # ── Tie hidden toggle to pill updates ─────────────────────────────
        self.ready_toggle.toggled.connect(self._on_ready_ui_update)
        # Manually trigger initial state to configure colors properly
        self._on_ready_ui_update(self.ready_toggle.isChecked())

        # Start the client on launch with saved settings
        self.fl_worker.start_fl_client(
            self.server_address, 
            self.local_epochs, 
            self.batch_size, 
            self.learning_rate
        )

    @Slot(str, int, int, float)
    def _on_sync_requested(self, server_address: str, local_epochs: int, batch_size: int, lr: float):
        # Save settings when updated
        self.settings.setValue("server_address", server_address)
        self.settings.setValue("local_epochs", local_epochs)
        self.settings.setValue("batch_size", batch_size)
        self.settings.setValue("learning_rate", lr)
        
        self.server_addr_lbl.setText(server_address)

        # Pass to worker
        self.fl_worker.start_fl_client(server_address, local_epochs, batch_size, lr)

    # ──────────────────────────────────────────────────────────────────────
    #  Topbar
    # ──────────────────────────────────────────────────────────────────────
    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("Topbar")

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(20)

        # Hidden Checkbox functioning as logical state (Client is ready/paused)
        self.ready_toggle = QCheckBox()
        self.ready_toggle.setChecked(True)
        self.ready_toggle.hide()

        # ── Left side: page title ────────────────────────────────────────
        left_group = QHBoxLayout()
        left_group.setSpacing(16)

        self.page_title_lbl = QLabel(TAB_TITLES[TAB_DASHBOARD])
        self.page_title_lbl.setObjectName("TopbarTitle")

        left_group.addWidget(self.page_title_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(left_group)
        layout.addStretch()

        # ── Right side: ready pill + server addr + node badge ────────────
        right_group = QHBoxLayout()
        right_group.setSpacing(16)

        # Ready Status Pill (Togglable visually, logic relies on `ready_toggle`)
        self.ready_pill = QFrame()
        self.ready_pill.setObjectName("EtlPill")
        self.ready_pill.setFixedHeight(26)
        self.ready_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ready_pill.mousePressEvent = lambda e: self.ready_toggle.toggle()

        pill_layout = QHBoxLayout(self.ready_pill)
        pill_layout.setContentsMargins(10, 4, 10, 4)
        pill_layout.setSpacing(6)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #0d9488; font-size: 8px;")

        self.status_label = QLabel("Node: Ready")
        self.status_label.setObjectName("EtlText")

        pill_layout.addWidget(self.status_dot)
        pill_layout.addWidget(self.status_label)

        right_group.addWidget(self.ready_pill)

        # Vertical divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet("color: #cbd5e1;")
        div.setFixedWidth(1)
        right_group.addWidget(div)

        # Server info
        server_col = QWidget()
        server_col.setStyleSheet("background: transparent; border: none;")
        server_layout = QVBoxLayout(server_col)
        server_layout.setContentsMargins(0, 0, 0, 0)
        server_layout.setSpacing(2)
        server_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)


        server_lbl_title = QLabel("SERVER ADDR")
        server_lbl_title.setStyleSheet(
            "font-size: 9px; font-weight: 800; color: #64748b; letter-spacing: 0.5px; border: none;"
        )
        server_lbl_title.setAlignment(Qt.AlignmentFlag.AlignRight)

        node_id = os.environ.get("CLIENT_ID", "1")
        self.server_addr_lbl = QLabel(self.server_address)
        self.server_addr_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #1e293b; border: none;")
        self.server_addr_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        server_layout.addWidget(server_lbl_title)
        server_layout.addWidget(self.server_addr_lbl)

        # Node badge
        self.node_badge = QLabel(node_id)
        self.node_badge.setObjectName("NodeBadge")
        self.node_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        right_group.addWidget(server_col)
        right_group.addWidget(self.node_badge)

        layout.addLayout(right_group)

        return topbar

    # ──────────────────────────────────────────────────────────────────────
    #  Slots
    # ──────────────────────────────────────────────────────────────────────
    @Slot(int)
    def _on_tab_changed(self, index: int):
        """Switch content stack and update topbar title + sidebar selection."""
        self.content_stack.setCurrentIndex(index)
        self.page_title_lbl.setText(TAB_TITLES.get(index, ""))
        # Keep sidebar in sync if triggered programmatically (e.g. from dashboard link)
        self.sidebar.set_active_tab(index)

    @Slot(bool)
    def _on_ready_ui_update(self, checked: bool):
        """Update the pill UI when the hidden toggle changes."""
        if checked:
            self.status_dot.setStyleSheet("color: #0d9488; font-size: 8px;")
            self.status_label.setText("Node: Ready")
            self.status_label.setStyleSheet(
                "font-size: 9.5px; font-weight: 800; color: #0f766e; letter-spacing: 1px;"
            )
            self.ready_pill.setObjectName("EtlPill")
        else:
            self.status_dot.setStyleSheet("color: #ef4444; font-size: 8px;")
            self.status_label.setText("Node: Paused")
            self.status_label.setStyleSheet(
                "font-size: 9.5px; font-weight: 800; color: #b45309; letter-spacing: 1px;"
            )
            self.ready_pill.setObjectName("EtlPillInactive")
        self.on_ready_toggled(checked)

    @Slot(bool)
    def on_ready_toggled(self, checked: bool):
        """Single source of truth for client readiness."""
        if checked:
            self.fl_worker.resume_fl_client()
            print("[SYSTEM] Resuming participation (Ready)")
        else:
            self.fl_worker.stop_fl_client()
            print("[SYSTEM] Pausing participation (Not Ready)")

        self.config_tab.set_ready_state(checked)

    @Slot()
    def on_mute_rejected(self):
        """Snap the toggle back if mute was rejected (mid-training)."""
        self.ready_toggle.blockSignals(True)
        self.ready_toggle.setChecked(True)
        self.ready_toggle.blockSignals(False)
        self.fl_worker.log_message.emit(
            "[WARNING] Mute rejected — client is currently training. "
            "Try again after the round completes."
        )

    # ──────────────────────────────────────────────────────────────────────
    #  Style loading
    # ──────────────────────────────────────────────────────────────────────
    def load_resources(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))

        if os.getenv("DEV_MODE") == "0":
            file = QFile(":/ui/assets/style.qss")
            if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
                self.setStyleSheet(QTextStream(file).readAll())
        else:
            qss_path = os.path.join(base_dir, "assets", "style.qss")
            try:
                with open(qss_path, "r") as f:
                    self.setStyleSheet(f.read())
                    print(f"[STYLE] Loaded QSS from: {qss_path}")
            except FileNotFoundError:
                print(f"[STYLE] ❌ Not found: {qss_path}")        # Load Fonts
        font_path = os.path.join(base_dir, "fonts", "Inter-Regular.ttf")
        if os.path.exists(font_path):
            QFontDatabase.addApplicationFont(font_path)
        else:
            # Fallback for resource-based loading or relative paths
            QFontDatabase.addApplicationFont("fonts/Inter-Regular.ttf")

    # ──────────────────────────────────────────────────────────────────────
    #  Graceful shutdown
    # ──────────────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        print("[SYSTEM] Shutting down workers…")

        for sig in (self.fl_worker.mute_rejected, self.fl_worker.fl_client_stopped):
            try:
                sig.disconnect()
            except Exception:
                pass

        worker = getattr(self.fl_worker, "fl_system_worker", None)
        if worker and worker.fl_client:
            try:
                worker.fl_client.unmute()
            except Exception:
                pass

        self.fl_worker.shutdown()
        self.worker_thread.quit()
        self.worker_thread.wait(3000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClientUi()
    window.show()
    sys.exit(app.exec())
