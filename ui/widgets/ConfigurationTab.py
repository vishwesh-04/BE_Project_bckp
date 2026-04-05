from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                               QLabel, QLineEdit, QPushButton)
from PySide6.QtCore import Qt, Signal
from ui.widgets.DashboardCard import DashboardCard
from ui.widgets.LogsDialog import LogsDialog


class ConfigurationTab(QWidget):
    # Signal emitted when the server address is successfully updated
    server_updated = Signal(str)

    def __init__(self):
        super().__init__()
        # Main layout for the whole tab
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(25)

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

        # Add the other two (non-interactive or connected elsewhere)
        stats_layout.addWidget(DashboardCard("Resource Status", "Optimized", "GPU Acceleration Active", "#3b82f6"))
        stats_layout.addWidget(DashboardCard("Data Quality Alert", "3% Outliers", "View Quality Report", "#f43f5e"))

        self.layout.addLayout(stats_layout)

    def show_logs(self):
        """Slot to open the logs dialog."""
        dialog = LogsDialog(self)
        dialog.exec()

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
        self.server_input = QLineEdit("https://api.medlink-fl.io/v1")
        self.server_input.setProperty("class", "EnvInput")
        self.server_input.setPlaceholderText("Enter Federated Server URL...")
        self.server_input.setFixedHeight(40)

        self.set_btn = QPushButton("SET ENDPOINT")
        self.set_btn.setFixedWidth(120)
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

        params = [
            ("LOCAL EPOCHS", "3"),
            ("BATCH SIZE", "32"),
            ("LEARNING RATE", "0.001")
        ]

        for label_text, default_val in params:
            v_box = QVBoxLayout()
            v_box.setSpacing(8)

            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 700;")

            edit = QLineEdit(default_val)
            edit.setProperty("class", "EnvInput")

            v_box.addWidget(lbl)
            v_box.addWidget(edit)
            grid_layout.addLayout(v_box)

        card_layout.addWidget(inputs_widget)
        self.layout.addWidget(card)

    def _init_action_buttons(self):
        """Creates the primary sync button at the bottom."""
        btn_layout = QHBoxLayout()

        sync_btn = QPushButton("MANUALLY SYNCHRONIZE WEIGHTS")
        sync_btn.setProperty("class", "PrimaryButton")
        sync_btn.setFixedHeight(50)
        sync_btn.setCursor(Qt.PointingHandCursor)

        btn_layout.addWidget(sync_btn)
        self.layout.addLayout(btn_layout)

    def handle_server_change(self):
        """Handles updating the server endpoint."""
        new_url = self.server_input.text()
        print(f"[SYSTEM] Server address set to: {new_url}")
        self.server_updated.emit(new_url)