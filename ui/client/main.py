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
        # 1. Configuration Tab (start + real-time training status)
        self.config_tab.sync_requested.connect(self.fl_worker.start_fl_client)
        # NOTE: stop_requested removed — topbar toggle is the sole readiness control.
        self.fl_worker.training_started.connect(self.config_tab.on_training_started)
        self.fl_worker.training_ended.connect(self.config_tab.on_training_ended)
        
        # Connect client started / stopped signals to UI
        self.fl_worker.fl_client_started.connect(self.config_tab.on_fl_client_started)
        self.fl_worker.fl_client_stopped.connect(self.config_tab.on_fl_client_stopped)
        
        # Snap checkbox back when mute is rejected (client is mid-training)
        self.fl_worker.mute_rejected.connect(self.on_mute_rejected)
        
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
        
        # Ready Toggle — the SINGLE source of truth for client readiness
        self.ready_toggle = QCheckBox("Ready")
        self.ready_toggle.setChecked(True)
        self.ready_toggle.setToolTip("Toggle to pause/resume participating in federated rounds.")
        self.ready_toggle.toggled.connect(self.on_ready_toggled)
        self.ready_toggle.setStyleSheet("font-weight: bold; color: #0d9488;")
        
        topbar_layout.addWidget(self.ready_toggle)
        topbar_layout.addWidget(QLabel(f"  NODE_{os.environ.get('CLIENT_ID', 'DEFAULT')}"))

        right_layout.addWidget(topbar)
        right_layout.addWidget(self.content_stack)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(right_container)

        main_layout.setStretch(0, 1)
        main_layout.setStretch(1, 4)

    def on_ready_toggled(self, checked: bool):
        """
        Single source of truth for client readiness.
        Routes directly to the thread-safe mute/unmute API on the worker.
        Also updates the config tab's training card for visual consistency.
        """
        # Route through the worker's mute/unmute API so the
        # FLClientRuntime._muted Event is updated correctly on the FL thread.
        if checked:
            self.fl_worker.resume_fl_client()
            print("[SYSTEM] Resuming participation (Ready)")
        else:
            self.fl_worker.stop_fl_client()
            print("[SYSTEM] Pausing participation (Not Ready)")

        # Reflect the new readiness in the config tab's training card
        # (no-op if not connected — set_ready_state checks internally).
        self.config_tab.set_ready_state(checked)

    def on_mute_rejected(self):
        """
        Called when mute() was rejected because a training round is in progress.
        Snap the checkbox back to checked (Ready) so the UI matches reality.
        """
        # Block signals temporarily to avoid triggering on_ready_toggled again.
        self.ready_toggle.blockSignals(True)
        self.ready_toggle.setChecked(True)
        self.ready_toggle.blockSignals(False)
        print(
            "[SYSTEM] Cannot pause: training round in progress. "
            "Toggle will re-enable after the round completes."
        )
        self.fl_worker.log_message.emit(
            "[WARNING] Mute rejected — client is currently training. "
            "Try again after the round completes."
        )

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
        """Graceful shutdown: stop workers before Qt tears down C++ objects."""
        print("[SYSTEM] Application closing, shutting down workers...")

        # 1. Defensively disconnect signals that could fire into dead objects
        #    after threads are terminated.
        for sig in (self.fl_worker.mute_rejected, self.fl_worker.fl_client_stopped):
            try:
                sig.disconnect()
            except Exception:
                pass

        # 2. Directly unmute the runtime (no signal emission — we're closing).
        worker = getattr(self.fl_worker, 'fl_system_worker', None)
        if worker and worker.fl_client:
            try:
                worker.fl_client.unmute()  # release any held lock cleanly
            except Exception:
                pass

        # 3. Shut down background threads (terminates the blocked gRPC call).
        self.fl_worker.shutdown()

        # 4. Quit the outer worker_thread (the one FLWorker was moved to).
        self.worker_thread.quit()
        self.worker_thread.wait(3000)  # wait up to 3s

        event.accept()



if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClientUi()
    window.show()
    sys.exit(app.exec())
