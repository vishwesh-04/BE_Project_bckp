from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot
import os
from ui.widgets.LogsDialog import LogsDialog


class _ToggleSwitch(QFrame):
    """
    A simple toggle-switch widget that mimics the HTML prototype's pill toggles.
    States: ON (teal bg, knob right) / OFF (slate bg, knob left).
    """

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(40, 22)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        if self._checked:
            self.setStyleSheet(
                "background-color: #0d9488; border-radius: 11px;"
            )
        else:
            self.setStyleSheet(
                "background-color: #e2e8f0; border-radius: 11px;"
            )
        # The knob is a child widget
        if not hasattr(self, "_knob"):
            self._knob = QFrame(self)
            self._knob.setFixedSize(14, 14)
            self._knob.setStyleSheet(
                "background-color: white; border-radius: 7px;"
            )
        knob_x = 22 if self._checked else 4
        self._knob.move(knob_x, 4)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._apply_style()
        super().mousePressEvent(event)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, val: bool):
        self._checked = val
        self._apply_style()


class ConfigurationTab(QWidget):
    """
    Tab 4 — Node Settings
    Matches the HTML prototype 'settings' section:
      2×2 grid of cards:
        1. Network & Transport   2. Client Identity
        3. Warehouse & ETL       4. Privacy & Security
      + Discard / Update Connection & Restart buttons

    All existing signals and slots are preserved.
    """

    # ── Existing signals (must remain unchanged for main.py wiring) ──────
    server_updated = Signal(str)
    sync_requested = Signal(str, int, int, float)
    etl_toggled    = Signal(bool)

    def __init__(self):
        super().__init__()
        self.logs_dialog = LogsDialog(self)
        
        self._etl_active = False

        # Outer scroll area so content doesn't clip on small screens
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: #f8fafc;")

        content = QWidget()
        content.setStyleSheet("background: #f8fafc;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(24)

        # 2 × 2 grid of setting cards
        grid = QGridLayout()
        grid.setSpacing(20)

        grid.addWidget(self._build_network_card(),   0, 0)
        grid.addWidget(self._build_identity_card(),  0, 1)
        grid.addWidget(self._build_warehouse_card(), 1, 0)
        grid.addWidget(self._build_privacy_card(),   1, 1)

        content_layout.addLayout(grid)

        # Bottom action row
        content_layout.addLayout(self._build_action_row())
        content_layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ================================================================== #
    #  Card builders                                                       #
    # ================================================================== #

    def _build_network_card(self) -> QFrame:
        """Network & Transport card."""
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        lay.addWidget(self._card_header(
            "Network &amp; Transport",
            # WiFi/cloud SVG icon path (inline color)
            "#0d9488"
        ))

        # FL Aggregator address
        lay.addWidget(self._field_label("FL AGGREGATOR ADDRESS"))
        self.server_input = QLineEdit("127.0.0.1:45678")
        self.server_input.setProperty("class", "EnvInput")
        self.server_input.setFixedHeight(36)
        lay.addWidget(self.server_input)

        # TLS toggle row
        tls_row = QHBoxLayout()
        tls_info = QVBoxLayout()
        tls_title = QLabel("TLS Encryption")
        tls_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        tls_sub = QLabel("Enable secure communication tunnels")
        tls_sub.setStyleSheet("font-size: 10px; color: #64748b;")
        tls_info.addWidget(tls_title)
        tls_info.addWidget(tls_sub)
        self._tls_toggle = _ToggleSwitch(checked=False)
        tls_row.addLayout(tls_info)
        tls_row.addStretch()
        tls_row.addWidget(self._tls_toggle)
        lay.addLayout(tls_row)

        # CA Cert path
        lay.addWidget(self._field_label("CA CERTIFICATE PATH"))
        self._ca_cert_input = QLineEdit()
        self._ca_cert_input.setPlaceholderText("/app/certs/ca.pem")
        self._ca_cert_input.setProperty("class", "EnvInput")
        self._ca_cert_input.setFixedHeight(36)
        lay.addWidget(self._ca_cert_input)

        return card

    def _build_identity_card(self) -> QFrame:
        """Client Identity card."""
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        lay.addWidget(self._card_header("Client Identity", "#0d9488"))

        lay.addWidget(self._field_label("NODE IDENTIFIER"))
        self._node_id_input = QLineEdit(os.getenv("CLIENT_ID", "1"))
        self._node_id_input.setProperty("class", "EnvInput")
        self._node_id_input.setFixedHeight(36)
        lay.addWidget(self._node_id_input)

        # Local Personalization toggle
        lp_row = QHBoxLayout()
        lp_info = QVBoxLayout()
        lp_title = QLabel("Local Personalization")
        lp_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        lp_sub = QLabel("Fine-tune model to local data distribution")
        lp_sub.setStyleSheet("font-size: 10px; color: #64748b;")
        lp_info.addWidget(lp_title)
        lp_info.addWidget(lp_sub)
        self._personalize_toggle = _ToggleSwitch(checked=False)
        lp_row.addLayout(lp_info)
        lp_row.addStretch()
        lp_row.addWidget(self._personalize_toggle)
        lay.addLayout(lp_row)

        # Deployment Target
        lay.addWidget(self._field_label("DEPLOYMENT TARGET"))
        self._deploy_combo = QComboBox()
        self._deploy_combo.addItems([
            "Flower ClientApp (Docker)",
            "EHR On-Premise Binary",
            "Hybrid Edge Simulation",
        ])
        lay.addWidget(self._deploy_combo)

        return card

    def _build_warehouse_card(self) -> QFrame:
        """Warehouse & ETL card."""
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        lay.addWidget(self._card_header("Warehouse &amp; ETL", "#0d9488"))

        lay.addWidget(self._field_label("SOURCE TYPE"))
        self._src_combo = QComboBox()
        self._src_combo.addItems([
            "PostgreSQL (Central Warehouse)",
            "MS SQL Server (Hospital EHR)",
            "Snowflake Cloud",
            "FHIR API / HL7 Stream",
        ])
        lay.addWidget(self._src_combo)

        lay.addWidget(self._field_label("CONNECTION URI / HOST"))
        self._conn_uri_input = QLineEdit("********")
        self._conn_uri_input.setEchoMode(QLineEdit.Password)
        self._conn_uri_input.setProperty("class", "EnvInput")
        self._conn_uri_input.setFixedHeight(36)
        # Monospace font for URI
        self._conn_uri_input.setStyleSheet(
            "font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 12px;"
        )
        lay.addWidget(self._conn_uri_input)

        lay.addWidget(self._field_label("TRAINING VIEW / QUERY"))
        self._query_edit = QTextEdit()
        self._query_edit.setPlainText(
            "SELECT * FROM clinical.v_patient_outcomes WHERE anonymized = TRUE"
        )
        self._query_edit.setFixedHeight(60)
        self._query_edit.setStyleSheet(
            "background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; "
            "font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 10px; "
            "color: #1e293b; padding: 6px;"
        )
        lay.addWidget(self._query_edit)

        # ETL toggle button (connects to existing signal)
        self.etl_btn = QPushButton("TOGGLE ETL PIPELINE")
        self.etl_btn.setProperty("class", "SecondaryButton")
        self.etl_btn.setFixedHeight(36)
        self.etl_btn.setCursor(Qt.PointingHandCursor)
        self.etl_btn.clicked.connect(self._on_etl_clicked)
        lay.addWidget(self.etl_btn)

        return card

    def _build_privacy_card(self) -> QFrame:
        """Privacy & Security card."""
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        lay.addWidget(self._card_header("Privacy &amp; Security", "#0d9488"))

        # SecAgg+ toggle (ON by default)
        secagg_row = QHBoxLayout()
        secagg_info = QVBoxLayout()
        secagg_title = QLabel("Flower SecAgg+")
        secagg_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        secagg_sub = QLabel("Secure aggregation via multi-party computation")
        secagg_sub.setStyleSheet("font-size: 10px; color: #64748b;")
        secagg_sub.setWordWrap(True)
        secagg_info.addWidget(secagg_title)
        secagg_info.addWidget(secagg_sub)
        self._secagg_toggle = _ToggleSwitch(checked=True)
        secagg_row.addLayout(secagg_info)
        secagg_row.addStretch()
        secagg_row.addWidget(self._secagg_toggle)
        lay.addLayout(secagg_row)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #f1f5f9; border: none;")
        lay.addWidget(div)

        # Local DP toggle (OFF by default)
        dp_row = QHBoxLayout()
        dp_info = QVBoxLayout()
        dp_title = QLabel("Local Differential Privacy")
        dp_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        dp_sub = QLabel("Add noise to weights before transmission")
        dp_sub.setStyleSheet("font-size: 10px; color: #64748b;")
        dp_info.addWidget(dp_title)
        dp_info.addWidget(dp_sub)
        self._dp_toggle = _ToggleSwitch(checked=False)
        dp_row.addLayout(dp_info)
        dp_row.addStretch()
        dp_row.addWidget(self._dp_toggle)
        lay.addLayout(dp_row)

        # Audit Log Level
        lay.addWidget(self._field_label("AUDIT LOG LEVEL"))
        self._log_combo = QComboBox()
        self._log_combo.addItems([
            "CRITICAL (Production)",
            "INFO (Standard)",
            "DEBUG (Development)",
        ])
        self._log_combo.setCurrentIndex(1)   # INFO default
        lay.addWidget(self._log_combo)

        # Epoch / batch / lr fields (keep existing runtime params)
        lay.addWidget(self._field_label("LOCAL EPOCHS"))
        self.epochs_input = QLineEdit("3")
        self.epochs_input.setProperty("class", "EnvInput")
        self.epochs_input.setFixedHeight(32)
        lay.addWidget(self.epochs_input)

        row_bl = QHBoxLayout()
        row_bl.setSpacing(12)

        bs_col = QVBoxLayout()
        bs_col.addWidget(self._field_label("BATCH SIZE"))
        self.batch_input = QLineEdit("32")
        self.batch_input.setProperty("class", "EnvInput")
        self.batch_input.setFixedHeight(32)
        bs_col.addWidget(self.batch_input)

        lr_col = QVBoxLayout()
        lr_col.addWidget(self._field_label("LEARNING RATE"))
        self.lr_input = QLineEdit("0.001")
        self.lr_input.setProperty("class", "EnvInput")
        self.lr_input.setFixedHeight(32)
        lr_col.addWidget(self.lr_input)

        row_bl.addLayout(bs_col)
        row_bl.addLayout(lr_col)
        lay.addLayout(row_bl)

        return card

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()

        discard_btn = QPushButton("DISCARD")
        discard_btn.setFixedHeight(38)
        discard_btn.setMinimumWidth(120)
        discard_btn.setProperty("class", "SecondaryButton")
        discard_btn.setCursor(Qt.PointingHandCursor)

        self.set_btn = QPushButton("UPDATE CONNECTION & RESTART")
        self.set_btn.setFixedHeight(38)
        self.set_btn.setMinimumWidth(220)
        self.set_btn.setStyleSheet(
            "background-color: #0d9488; color: white; font-weight: 800; "
            "font-size: 10px; letter-spacing: 1px; border-radius: 10px; border: none;"
        )
        self.set_btn.setCursor(Qt.PointingHandCursor)
        self.set_btn.clicked.connect(self.handle_server_change)

        row.addWidget(discard_btn)
        row.addWidget(self.set_btn)
        return row

    # ================================================================== #
    #  Styling helpers                                                     #
    # ================================================================== #

    @staticmethod
    def _card() -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")
        return card

    @staticmethod
    def _card_header(title_html: str, _icon_color: str) -> QFrame:
        """Renders a card section header with a title label and bottom divider."""
        header = QFrame()
        header.setStyleSheet(
            "border: none; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px;"
        )
        lay = QHBoxLayout(header)
        lay.setContentsMargins(0, 0, 0, 8)
        lbl = QLabel(title_html)
        lbl.setTextFormat(Qt.RichText)
        lbl.setStyleSheet(
            "font-size: 12px; font-weight: 800; color: #1e293b; "
            "letter-spacing: 0.5px; border: none;"
        )
        lay.addWidget(lbl)
        return header

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #94a3b8; font-size: 9px; font-weight: 800; letter-spacing: 1px;"
        )
        return lbl

    # ================================================================== #
    #  Preserved existing slots & signal handlers                         #
    # ================================================================== #

    def show_logs(self):
        """Slot to open the logs dialog."""
        self.logs_dialog.show()

    @Slot(str)
    def append_log(self, msg: str):
        color = "#f8fafc"
        if "ERROR" in msg or "Exception" in msg:
            color = "#ef4444"
        elif "WARNING" in msg:
            color = "#f59e0b"
        elif "INFO" in msg or "SYSTEM" in msg:
            color = "#38bdf8"
        msg_html = msg.replace('\n', '<br>')
        html = f'<div style="color: {color}; margin-bottom: 4px;">{msg_html}</div>'
        self.logs_dialog.append_log(html)

    @Slot(int)
    def on_training_started(self, round_num: int = 0):
        self.set_btn.setText(f"TRAINING ROUND {round_num}…")
        self.set_btn.setEnabled(False)

    @Slot(bool)
    def on_training_ended(self, success: bool):
        self.set_btn.setText("UPDATE CONNECTION & RESTART")
        self.set_btn.setEnabled(True)

    @Slot()
    def on_fl_client_started(self):
        self._set_ui_state_connected(True)

    @Slot(bool, str)
    def on_fl_client_stopped(self, success: bool, message: str):
        is_pause_event = success and "Paused" in message
        if not is_pause_event:
            self._set_ui_state_connected(False)
        if not success:
            self.append_log(f"[ERROR] {message}")

    def _set_ui_state_connected(self, connected: bool):
        if connected:
            self.set_btn.setText("CONNECTED")
            self.set_btn.setEnabled(False)
            self.server_input.setReadOnly(True)
            self.epochs_input.setReadOnly(True)
            self.batch_input.setReadOnly(True)
            self.lr_input.setReadOnly(True)
        else:
            self.set_btn.setText("UPDATE CONNECTION & RESTART")
            self.set_btn.setEnabled(True)
            self.server_input.setReadOnly(False)
            self.epochs_input.setReadOnly(False)
            self.batch_input.setReadOnly(False)
            self.lr_input.setReadOnly(False)

    @Slot(bool)
    def set_ready_state(self, is_ready: bool):
        pass  # Visual readiness reflected in topbar; config tab has no dedicated widget for this

    def _on_etl_clicked(self):
        self._etl_active = not self._etl_active
        self.etl_toggled.emit(self._etl_active)

    @Slot()
    def toggle_etl(self):
        self._on_etl_clicked()

    @Slot(bool)
    def set_etl_active(self, active: bool):
        self._etl_active = active
        if active:
            self.etl_btn.setText("ETL PIPELINE: ACTIVE")
        else:
            self.etl_btn.setText("TOGGLE ETL PIPELINE")

    def handle_server_change(self):
        """Handles updating server endpoint and connecting — preserves original logic."""
        new_url = self.server_input.text().strip()
        try:
            epochs     = int(self.epochs_input.text())
            batch_size = int(self.batch_input.text())
            lr         = float(self.lr_input.text())
        except ValueError:
            self.append_log("[ERROR] Invalid numeric parameters.")
            return

        self.server_updated.emit(new_url)

        url = new_url.replace("https://", "").replace("http://", "")
        if url.endswith("/v1"):
            url = url.replace("/v1", "")
        if ":" not in url:
            url = url + ":8080"

        self.append_log(f"[SYSTEM] Requesting sync to: {url}")
        self.sync_requested.emit(url, epochs, batch_size, lr)
