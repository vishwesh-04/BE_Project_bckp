from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                               QLabel, QLineEdit, QPushButton)
from PySide6.QtCore import Qt, Signal, Slot
import torch
import os
from common.config import CLIENT_ID
from ui.widgets.DashboardCard import DashboardCard
from ui.widgets.LogsDialog import LogsDialog


class ConfigurationTab(QWidget):
    # Signal emitted when the server address is successfully updated
    server_updated = Signal(str)
    # Signal to request starting the FL Client node (url, epochs, batch_size, lr)
    sync_requested = Signal(str, int, int, float)

    def __init__(self):
        super().__init__()
        # Main layout for the whole tab
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(25)
        
        self.logs_dialog = LogsDialog(self)

        # 1. Stats Row (Top)
        self._init_stats_row()

        # 2. Server Configuration Card (Middle-Top)
        self._init_server_card()

        # 3. Training Parameters Card (Middle-Bottom)
        self._init_runtime_card()

        # 4. Action Buttons (Bottom)
        self._init_action_buttons()

        # Pushes everything to the top
        self.layout.addStretch()

    def _init_stats_row(self):
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)

        # 1. Create the specific card
        self.training_card = DashboardCard(
            "Local Training Round", "Round 14", "Accuracy: 84.1%",
            "#0d9488", "(View Logs)"
        )

        # 2. Connect its signal
        self.training_card.clicked.connect(self.show_logs)

        stats_layout.addWidget(self.training_card)

        # 3. Dynamic Hardware checks
        has_gpu = torch.cuda.is_available()
        gpu_stat = "GPU Acceleration Active" if has_gpu else "CPU Execution"
        gpu_color = "#3b82f6" if has_gpu else "#64748b"
        
        node_name = os.getenv("CLIENT_ID", CLIENT_ID)
        node_label = node_name[:12] if node_name else "Unassigned"

        # Add the other two (non-interactive or connected elsewhere)
        stats_layout.addWidget(DashboardCard("Resource Status", "Active", gpu_stat, gpu_color))
        stats_layout.addWidget(DashboardCard("Node Identity", node_label, "Connected and Authenticated" if node_name else "Unknown Node", "#f43f5e" if not node_name else "#0d9488"))

        self.layout.addLayout(stats_layout)

    def show_logs(self):
        """Slot to open the logs dialog."""
        self.logs_dialog.show()

    @Slot(str)
    def append_log(self, msg: str):
        color = "#f8fafc"
        if "ERROR" in msg or "Exception" in msg: color = "#ef4444"
        elif "WARNING" in msg: color = "#f59e0b"
        elif "INFO" in msg or "SYSTEM" in msg: color = "#38bdf8"
        
        # Replace newlines with <br> for HTML rendering
        msg_html = msg.replace('\n', '<br>')
        html = f'<div style="color: {color}; margin-bottom: 4px;">{msg_html}</div>'
        self.logs_dialog.append_log(html)

    @Slot()
    def on_training_started(self):
        self.training_card.update_content("Status: Training", "Training local model...", "#f59e0b")

    @Slot(bool)
    def on_training_ended(self, success: bool):
        if success:
            self.training_card.update_content("Status: Round Complete", "Weights synchronized", "#0d9488")
        else:
            self.training_card.update_content("Status: Failed", "Training encountered an error", "#ef4444")

    @Slot()
    def on_fl_client_started(self):
        self.training_card.update_content("Status: Connected", "Listening for server...", "#0d9488")
        self._set_ui_state_connected(True)

    @Slot(bool, str)
    def on_fl_client_stopped(self, success: bool, message: str):
        if success:
            if "Paused" in message:
                # This branch is reached when the topbar toggle mutes the client
                # while connected — client stays connected but skips rounds.
                self.training_card.update_content("Status: Paused", "Not participating (muted)", "#f59e0b")
            else:
                self.training_card.update_content("Status: Idle", "Disconnected from server", "#3b82f6")
                self._set_ui_state_connected(False)
        else:
            self.training_card.update_content("Status: Error", "Connection failed. Check logs.", "#ef4444")
            self.append_log(f"[ERROR] {message}")
            self._set_ui_state_connected(False)

    def _set_ui_state_connected(self, connected: bool):
        if connected:
            self.set_btn.setText("CONNECTED")
            self.set_btn.setEnabled(False)
            self.set_btn.setStyleSheet(
                "background-color: #334155; border-color: #334155; color: #64748b;"
            )
            self.server_input.setReadOnly(True)
            self.epochs_input.setReadOnly(True)
            self.batch_input.setReadOnly(True)
            self.lr_input.setReadOnly(True)
        else:
            self.set_btn.setText("CONNECT")
            self.set_btn.setEnabled(True)
            self.set_btn.setStyleSheet("")
            self.server_input.setReadOnly(False)
            self.epochs_input.setReadOnly(False)
            self.batch_input.setReadOnly(False)
            self.lr_input.setReadOnly(False)

    @Slot(bool)
    def set_ready_state(self, is_ready: bool):
        """
        Called by the topbar toggle to reflect readiness state in the training card
        WITHOUT modifying the connect/disconnect state of the button.
        Only takes effect when already connected (button is disabled / CONNECTED).
        """
        if not self.set_btn.isEnabled():  # i.e., currently connected
            if is_ready:
                self.training_card.update_content("Status: Connected", "Listening for server...", "#0d9488")
            else:
                self.training_card.update_content("Status: Paused", "Not participating (muted)", "#f59e0b")

    def _init_server_card(self):
        """Creates the card for setting the Federated Server URL."""
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("NETWORK CONFIGURATION")
        title.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title)

        input_row = QHBoxLayout()
        # Updated default network address
        self.server_input = QLineEdit("127.0.0.1:45678")
        self.server_input.setProperty("class", "EnvInput")
        self.server_input.setPlaceholderText("Enter Federated Server URL...")
        self.server_input.setFixedHeight(40)

        self.set_btn = QPushButton("CONNECT")
        self.set_btn.setFixedWidth(160)
        self.set_btn.setFixedHeight(40)
        self.set_btn.setProperty("class", "SecondaryButton")
        self.set_btn.setCursor(Qt.PointingHandCursor)
        self.set_btn.clicked.connect(self.handle_server_change)

        input_row.addWidget(self.server_input)
        input_row.addWidget(self.set_btn)
        layout.addLayout(input_row)

        self.layout.addWidget(card)

    def _init_runtime_card(self):
        """Creates the card for Local Epochs, Batch Size, and Learning Rate."""
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Inner Header
        header = QFrame()
        header.setStyleSheet("border-bottom: 1px solid #f1f5f9; padding: 15px;")
        h_layout = QHBoxLayout(header)
        title = QLabel("CLIENT RUNTIME ENVIRONMENT")
        title.setStyleSheet("font-style: italic; font-weight: 800; color: #334155; font-size: 11px;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        card_layout.addWidget(header)

        # Inputs Grid
        inputs_widget = QWidget()
        inputs_widget.setStyleSheet("padding: 20px;")
        grid_layout = QHBoxLayout(inputs_widget)
        grid_layout.setSpacing(20)

        self.epochs_input = QLineEdit("3")
        self.epochs_input.setProperty("class", "EnvInput")
        
        self.batch_input = QLineEdit("32")
        self.batch_input.setProperty("class", "EnvInput")
        
        self.lr_input = QLineEdit("0.001")
        self.lr_input.setProperty("class", "EnvInput")

        params = [
            ("LOCAL EPOCHS", self.epochs_input),
            ("BATCH SIZE", self.batch_input),
            ("LEARNING RATE", self.lr_input)
        ]

        for label_text, edit_widget in params:
            v_box = QVBoxLayout()
            v_box.setSpacing(8)

            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 700;")

            v_box.addWidget(lbl)
            v_box.addWidget(edit_widget)
            grid_layout.addLayout(v_box)

        card_layout.addWidget(inputs_widget)
        self.layout.addWidget(card)

    def _init_action_buttons(self):
        """Creates the primary sync button at the bottom."""
        pass

    def _emit_sync(self):
        url = self.server_input.text().strip()
        # Clean up URL for gRPC (Flower expects host:port, not http/https)
        url = url.replace("https://", "").replace("http://", "")
        if url.endswith("/v1"):
             url = url.replace("/v1", "")

        if ":" not in url:
             url = url + ":8080" # Default flower port

        print(f"[SYSTEM] Requesting sync to: {url}")
        self.training_card.update_content("Status: Connecting...", f"To {url}", "#f59e0b")
        self.sync_requested.emit(url)

    def handle_server_change(self):
        """Handles updating the server endpoint and connecting."""
        new_url = self.server_input.text()
        try:
            epochs = int(self.epochs_input.text())
            batch_size = int(self.batch_input.text())
            lr = float(self.lr_input.text())
        except ValueError:
            self.append_log("[ERROR] Invalid numeric parameters.")
            return

        print(f"[SYSTEM] Server address set to: {new_url}")
        self.server_updated.emit(new_url)
        
        # Clean up URL for gRPC (Flower expects host:port, not http/https)
        url = new_url.replace("https://", "").replace("http://", "")
        if url.endswith("/v1"):
             url = url.replace("/v1", "")

        if ":" not in url:
             url = url + ":8080" # Default flower port

        print(f"[SYSTEM] Requesting sync to: {url}")
        self.training_card.update_content("Status: Connecting...", f"To {url}", "#f59e0b")
        
        self.sync_requested.emit(url, epochs, batch_size, lr)
