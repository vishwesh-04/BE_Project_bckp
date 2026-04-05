from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                               QLabel, QLineEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QHeaderView, QAbstractItemView,
                               QScrollArea)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont


class InferenceTab(QWidget):
    # Future-proofing: Signal to tell the wrapper to verify a record
    verify_requested = Signal(str, bool)  # patient_id, is_correct

    def __init__(self):
        super().__init__()
        # Main Layout: [Left Column] | [Center Table] | [Right Drawer]
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # 1. LEFT COLUMN: Manual Inputs & Policy
        self.left_col = QVBoxLayout()
        self._setup_manual_tool()
        self.main_layout.addLayout(self.left_col, stretch=0)

        # 2. CENTER COLUMN: Warehouse Table & KPIs
        self.center_col = QVBoxLayout()
        self._setup_warehouse_view()
        self._setup_kpi_row()
        self.main_layout.addLayout(self.center_col, stretch=1)

        # 3. RIGHT COLUMN: The Detail Drawer (Hidden by default)
        self._setup_detail_drawer()
        self.main_layout.addWidget(self.detail_drawer)

    def _setup_manual_tool(self):
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")
        card.setFixedWidth(320)

        v_layout = QVBoxLayout(card)
        v_layout.setContentsMargins(20, 20, 20, 20)
        v_layout.setSpacing(15)

        title = QLabel("Manual Diagnostic Tool")
        title.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 13px;")
        v_layout.addWidget(title)

        for label in ["BLOOD GLUCOSE (MG/DL)", "AGE FACTOR", "BMI VALUE"]:
            l = QLabel(label)
            l.setStyleSheet("color: #94a3b8; font-size: 9px; font-weight: bold;")
            edit = QLineEdit()
            edit.setPlaceholderText("e.g. ...")
            edit.setProperty("class", "EnvInput")
            v_layout.addWidget(l)
            v_layout.addWidget(edit)

        predict_btn = QPushButton("PREDICT FOR PATIENT")
        predict_btn.setStyleSheet("""
            background-color: #1e293b; color: white; font-weight: bold; 
            padding: 12px; border-radius: 8px; margin-top: 5px;
        """)
        v_layout.addWidget(predict_btn)
        v_layout.addStretch()
        self.left_col.addWidget(card)

        # Policy Box
        policy = QFrame()
        policy.setStyleSheet("background-color: #1e3a8a; border-radius: 12px; padding: 15px;")
        p_layout = QVBoxLayout(policy)
        p_title = QLabel("CACHING POLICY")
        p_title.setStyleSheet("color: #93c5fd; font-size: 9px; font-weight: bold;")
        p_text = QLabel("Global model v4.2 is cached locally. Inference latency: ~14ms.")
        p_text.setWordWrap(True)
        p_text.setStyleSheet("color: white; font-size: 10px; line-height: 14px;")
        p_layout.addWidget(p_title)
        p_layout.addWidget(p_text)
        self.left_col.addWidget(policy)

    def _setup_warehouse_view(self):
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with Auto-Refresh toggle placeholder
        header_widget = QWidget()
        header_widget.setStyleSheet("padding: 15px 20px; border-bottom: 1px solid #f1f5f9;")
        h_layout = QHBoxLayout(header_widget)

        title = QLabel("Warehouse Records (Pending Review)")
        title.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 13px;")

        refresh_btn = QPushButton("Refresh Warehouse")
        refresh_btn.setStyleSheet("font-size: 10px; color: #0d9488; border: none; font-weight: bold;")

        h_layout.addWidget(title)
        h_layout.addStretch()
        h_layout.addWidget(refresh_btn)
        layout.addWidget(header_widget)

        # Table Setup
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["PATIENT ID", "METRIC", "PREDICTION", "ACTION"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { border: none; background: white; alternate-background-color: #f8fafc; }
            QHeaderView::section { background-color: #f8fafc; color: #94a3b8; font-weight: bold; border: none; padding: 10px; font-size: 10px; }
            QTableWidget::item { padding: 10px; border: none; }
        """)

        # Connect row click to show detail drawer
        self.table.itemClicked.connect(self._on_row_selected)

        # Mock Data
        self.add_table_row("W-1044", "Glucose: 122", "NEGATIVE", "#059669")
        self.add_table_row("W-1045", "Glucose: 189", "RISK DETECTED", "#dc2626")
        self.add_table_row("W-1046", "Glucose: 145", "PENDING AI...", "#94a3b8")

        layout.addWidget(self.table)
        self.center_col.addWidget(card)

    def _setup_kpi_row(self):
        row = QHBoxLayout()

        for icon, title, val, color in [
            ("💰", "Cost Saved", "$1,240 (Inference)", "#0d9488"),
            ("🛡️", "Compliance", "HIPAA Locked", "#2563eb")
        ]:
            card = QFrame()
            card.setObjectName("GlassCard")
            card.setProperty("class", "GlassCard")
            card.setFixedHeight(70)
            l = QHBoxLayout(card)

            ic = QLabel(icon)
            ic.setStyleSheet(f"font-size: 20px; background: #f8fafc; padding: 5px; border-radius: 8px;")

            info = QVBoxLayout()
            t = QLabel(title.upper());
            t.setStyleSheet("color: #94a3b8; font-size: 9px; font-weight: bold;")
            v = QLabel(val);
            v.setStyleSheet("color: #1e293b; font-size: 12px; font-weight: bold;")
            info.addWidget(t);
            info.addWidget(v)

            l.addWidget(ic);
            l.addLayout(info);
            l.addStretch()
            row.addWidget(card)

        self.center_col.addLayout(row)

    def _setup_detail_drawer(self):
        self.detail_drawer = QFrame()
        self.detail_drawer.setObjectName("GlassCard")
        self.detail_drawer.setProperty("class", "GlassCard")
        self.detail_drawer.setFixedWidth(350)
        self.detail_drawer.hide()  # Start hidden

        layout = QVBoxLayout(self.detail_drawer)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header with Close Button
        header = QHBoxLayout()
        self.drawer_title = QLabel("Patient Details")
        self.drawer_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #1e293b;")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("border: none; color: #94a3b8; font-weight: bold;")
        close_btn.clicked.connect(self.detail_drawer.hide)
        header.addWidget(self.drawer_title)
        header.addStretch()
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Evidence List (Master Lab Values)
        self.evidence_area = QScrollArea()
        self.evidence_area.setWidgetResizable(True)
        self.evidence_area.setStyleSheet("border: none; background: transparent;")

        container = QWidget()
        self.evidence_layout = QVBoxLayout(container)
        self.evidence_area.setWidget(container)
        layout.addWidget(self.evidence_area)

        # Action Row: Verify or Correct
        btn_row = QHBoxLayout()
        self.confirm_btn = QPushButton("Confirm Label")
        self.confirm_btn.setStyleSheet(
            "background: #0d9488; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")

        self.correct_btn = QPushButton("Correct")
        self.correct_btn.setStyleSheet(
            "background: white; border: 1px solid #e2e8f0; color: #ef4444; font-weight: bold; padding: 10px; border-radius: 6px;")

        btn_row.addWidget(self.confirm_btn)
        btn_row.addWidget(self.correct_btn)
        layout.addLayout(btn_row)

    def add_table_row(self, pid, metric, status, color):
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(pid))
        self.table.setItem(row, 1, QTableWidgetItem(metric))

        status_item = QTableWidgetItem(status)
        status_item.setForeground(QColor(color))
        font = status_item.font()
        font.setBold(True)
        status_item.setFont(font)
        self.table.setItem(row, 2, status_item)

        verify_btn = QPushButton("Inspect")
        verify_btn.setStyleSheet("color: #0d9488; font-weight: bold; border: none; background: transparent;")
        verify_btn.setCursor(Qt.PointingHandCursor)
        # Clicking "Inspect" triggers the same drawer logic
        verify_btn.clicked.connect(lambda: self._on_row_selected(self.table.item(row, 0)))
        self.table.setCellWidget(row, 3, verify_btn)

    def _clear_layout(self, layout):
        """Recursively clears widgets, sub-layouts, and spacers from a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self._clear_layout(item.layout())

    def _on_row_selected(self, item):
        """Populates the detail drawer when a row is selected."""
        row = item.row()
        patient_id = self.table.item(row, 0).text()

        # Safely clear all old widgets, sub-layouts, and spacers
        self._clear_layout(self.evidence_layout)

        self.drawer_title.setText(f"Analysis: {patient_id}")

        # Mocking 'Evidence Disclosure' - showing the real values from the warehouse
        labs = [
            ("Blood Glucose", "189 mg/dL", "+0.31 SHAP"),
            ("BMI", "28.4", "+0.15 SHAP"),
            ("Age Factor", "55", "+0.08 SHAP"),
            ("Physical Activity", "Moderate", "-0.09 SHAP")
        ]

        for name, val, impact in labs:
            l_row = QHBoxLayout()
            n_lbl = QLabel(name);
            n_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
            v_lbl = QLabel(val);
            v_lbl.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 11px;")
            l_row.addWidget(n_lbl);
            l_row.addStretch();
            l_row.addWidget(v_lbl)

            # Tiny impact indicator
            imp_lbl = QLabel(impact)
            imp_lbl.setStyleSheet(f"font-size: 9px; color: {'#ef4444' if '+' in impact else '#3b82f6'};")

            self.evidence_layout.addLayout(l_row)
            self.evidence_layout.addWidget(imp_lbl)
            self.evidence_layout.addSpacing(10)

        self.evidence_layout.addStretch()
        self.detail_drawer.show()