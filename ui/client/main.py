import sys
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QFrame, QLabel, QCheckBox
)
from PySide6.QtCore import Qt, QFile, QTextStream, QThread, Slot

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
        self.config_tab.sync_requested.connect(self.fl_worker.start_fl_client)
        self.fl_worker.training_started.connect(self.config_tab.on_training_started)
        self.fl_worker.training_ended.connect(self.config_tab.on_training_ended)
        self.fl_worker.fl_client_started.connect(self.config_tab.on_fl_client_started)
        self.fl_worker.fl_client_stopped.connect(self.config_tab.on_fl_client_stopped)
        self.fl_worker.mute_rejected.connect(self.on_mute_rejected)
        self.fl_worker.log_message.connect(self.config_tab.append_log)

        self.inference_tab.predict_requested.connect(self.fl_worker.run_prediction)
        self.fl_worker.prediction_result.connect(self.inference_tab.display_prediction_result)

        # ETL toggle: config tab → topbar indicator (and vice-versa via button)
        self.config_tab.etl_toggled.connect(self._on_etl_state_changed)

        # Dashboard "Edit Configuration" button → jump to settings tab
        self.dashboard_tab.goto_settings_requested.connect(
            lambda: self._on_tab_changed(TAB_SETTINGS)
        )
        self.dashboard_tab.open_logs_requested.connect(self.config_tab.show_logs)

        # History tab "View Logs" button → open logs dialog
        self.history_tab.open_logs_requested.connect(
            lambda _round: self.config_tab.show_logs()
        )

    # ──────────────────────────────────────────────────────────────────────
    #  Topbar
    # ──────────────────────────────────────────────────────────────────────
    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("Topbar")

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(20)

        # ── Left side: page title + ETL pill ─────────────────────────────
        left_group = QHBoxLayout()
        left_group.setSpacing(16)

        self.page_title_lbl = QLabel(TAB_TITLES[TAB_DASHBOARD])
        self.page_title_lbl.setObjectName("TopbarTitle")

        # ETL status pill
        etl_pill = QFrame()
        etl_pill.setObjectName("EtlPill")
        etl_layout = QHBoxLayout(etl_pill)
        etl_layout.setContentsMargins(10, 4, 10, 4)
        etl_layout.setSpacing(6)

        self.etl_dot = QLabel("●")
        self.etl_dot.setStyleSheet("color: #0d9488; font-size: 8px;")

        self.etl_label = QLabel("ETL Stream: Idle")
        self.etl_label.setObjectName("EtlText")

        etl_layout.addWidget(self.etl_dot)
        etl_layout.addWidget(self.etl_label)

        left_group.addWidget(self.page_title_lbl)
        left_group.addWidget(etl_pill)

        layout.addLayout(left_group)
        layout.addStretch()

        # ── Right side: ready toggle + server addr + node badge ───────────
        right_group = QHBoxLayout()
        right_group.setSpacing(20)

        # Ready / Mute toggle
        self.ready_toggle = QCheckBox("Ready")
        self.ready_toggle.setChecked(True)
        self.ready_toggle.setToolTip("Toggle to pause/resume participating in federated rounds.")
        self.ready_toggle.toggled.connect(self.on_ready_toggled)

        # Server info
        server_col = QWidget()
        server_layout = QVBoxLayout(server_col)
        server_layout.setContentsMargins(0, 0, 0, 0)
        server_layout.setSpacing(1)

        server_lbl_title = QLabel("SERVER ADDR")
        server_lbl_title.setObjectName("NodeInfoLabel")

        node_id = os.environ.get("CLIENT_ID", "1")
        self.server_addr_lbl = QLabel("127.0.0.1:45678")
        self.server_addr_lbl.setObjectName("NodeIdLabel")

        server_layout.addWidget(server_lbl_title)
        server_layout.addWidget(self.server_addr_lbl)

        # Node badge
        self.node_badge = QLabel(node_id)
        self.node_badge.setObjectName("NodeBadge")
        self.node_badge.setAlignment(Qt.AlignCenter)

        # Vertical divider
        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setStyleSheet("color: #e2e8f0;")
        div.setFixedWidth(1)

        right_group.addWidget(self.ready_toggle)
        right_group.addWidget(div)
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
    def _on_etl_state_changed(self, active: bool):
        """Update the topbar ETL indicator when the toggle is pressed."""
        if active:
            self.etl_dot.setStyleSheet("color: #f59e0b; font-size: 8px;")
            self.etl_label.setText("ETL Stream: Processing…")
            self.etl_label.setStyleSheet(
                "font-size: 9.5px; font-weight: 800; color: #b45309; letter-spacing: 1px;"
            )
        else:
            self.etl_dot.setStyleSheet("color: #0d9488; font-size: 8px;")
            self.etl_label.setText("ETL Stream: Idle")
            self.etl_label.setStyleSheet(
                "font-size: 9.5px; font-weight: 800; color: #0f766e; letter-spacing: 1px;"
            )

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
                print(f"[STYLE] ❌ Not found: {qss_path}")

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
