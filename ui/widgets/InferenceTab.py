from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from client.inference_engine import PredictionResult


class InferenceTab(QWidget):
    """
    Tab 1 — Live Prediction
    Matches the HTML prototype 'inference' section:
      - Left 1/3: Ad-hoc prediction card (3 inputs + Run button + result card)
      - Right 2/3: Live Pipeline Queue table card (with ETL toggle button)
    """

    # Signal to request a prediction from the FL worker
    predict_requested = Signal(dict)
    etl_toggle_requested = Signal()

    def __init__(self):
        super().__init__()

        root = QHBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(20)

        # Left: Ad-hoc prediction card (stretch=1)
        root.addWidget(self._build_prediction_card(), stretch=1)

        # Right: Pipeline queue table card (stretch=2)
        root.addWidget(self._build_queue_card(), stretch=2)

    # -------------------------------------------------------------------- #
    #  Left column — Ad-hoc Prediction                                      #
    # -------------------------------------------------------------------- #
    def _build_prediction_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Title
        title_row = QHBoxLayout()
        title = QLabel("Ad-hoc Prediction")
        title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #1e293b; letter-spacing: 0.5px; border: none;"
        )
        title_row.addWidget(title)
        layout.addLayout(title_row)

        # Three inputs
        self._inputs = {}
        fields = [
            ("glucose", "Serum Glucose", "120"),
            ("age",     "Patient Age",   "45"),
            ("bmi",     "Body Mass Index", "24.2"),
        ]
        for key, label_text, placeholder in fields:
            lbl = QLabel(label_text.upper())
            lbl.setStyleSheet(
                "color: #94a3b8; font-size: 9px; font-weight: 800; "
                "letter-spacing: 1px; border: none;"
            )
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            edit.setProperty("class", "EnvInput")
            edit.setFixedHeight(36)
            layout.addWidget(lbl)
            layout.addWidget(edit)
            self._inputs[key] = edit

        # Run button
        self._run_btn = QPushButton("PREDICT")
        self._run_btn.setProperty("class", "PrimaryButton")
        self._run_btn.setFixedHeight(42)
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.setStyleSheet(
            "background-color: #1e293b; color: white; font-weight: 800; "
            "font-size: 10px; letter-spacing: 1px; border-radius: 10px; "
            "border: none;"
        )
        self._run_btn.clicked.connect(self._emit_predict)
        layout.addWidget(self._run_btn)

        # Result card (hidden until result)
        self._result_card = QFrame()
        self._result_card.setObjectName("ResultCard")
        self._result_card.hide()
        rc_layout = QVBoxLayout(self._result_card)
        rc_layout.setContentsMargins(20, 16, 20, 16)
        rc_layout.setSpacing(4)

        score_row = QHBoxLayout()
        self._score_text_label = QLabel("RESULT SCORE")
        self._score_text_label.setStyleSheet(
            "font-size: 9px; font-weight: 800; color: #0f766e; letter-spacing: 1px; border: none;"
        )
        self._score_lbl = QLabel("0.0%")
        self._score_lbl.setStyleSheet(
            "font-size: 18px; font-weight: 900; color: #134e4a; border: none;"
        )
        score_row.addWidget(self._score_text_label)
        score_row.addStretch()
        score_row.addWidget(self._score_lbl)

        self._risk_lbl = QLabel("NEGATIVE / LOW RISK BASELINE")
        self._risk_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 800; color: #0f766e; letter-spacing: 0.5px; border: none;"
        )

        rc_layout.addLayout(score_row)
        rc_layout.addWidget(self._risk_lbl)

        self._result_card.setStyleSheet(
            "background: #f0fdfa; border: 1px solid #99f6e4; border-radius: 12px;"
        )
        layout.addWidget(self._result_card)
        layout.addStretch()

        return card

    # -------------------------------------------------------------------- #
    #  Right column — Live Pipeline Queue                                    #
    # -------------------------------------------------------------------- #
    def _build_queue_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Card header
        header = QFrame()
        header.setStyleSheet(
            "background: #f8fafc; border-bottom: 1px solid #f1f5f9; "
            "border-top-left-radius: 12px; border-top-right-radius: 12px;"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 12, 16, 12)

        h_title = QLabel("LIVE PIPELINE QUEUE")
        h_title.setStyleSheet(
            "color: #64748b; font-size: 10px; font-weight: 800; "
            "letter-spacing: 1px; background: transparent; border: none;"
        )

        self._etl_btn = QPushButton("TOGGLE ETL STATE")
        self._etl_btn.setStyleSheet(
            "font-size: 9px; font-weight: 800; color: #0d9488; "
            "border: 1px solid #99f6e4; background: transparent; "
            "border-radius: 4px; padding: 3px 8px; letter-spacing: 0.5px;"
        )
        self._etl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._etl_btn.setFixedHeight(24)
        self._etl_btn.clicked.connect(self.etl_toggle_requested.emit)

        h_layout.addWidget(h_title)
        h_layout.addStretch()
        h_layout.addWidget(self._etl_btn)
        layout.addWidget(header)

        # Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["RECORD UID", "PRIMARY METRIC", "LOCAL CONFIDENCE", "DECISION"]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.setStyleSheet("QTableWidget::item { border: none; }")

        # Pre-populate with prototype mock data
        self._add_queue_row("#ID-992", "Glucose: 98",  "99.8%", "LOW RISK",    "#059669", "#dcfce7")
        self._add_queue_row("#ID-993", "Glucose: 165", "88.4%", "ALERT RISK",  "#dc2626", "#fee2e2")

        layout.addWidget(self._table)
        return card

    # -------------------------------------------------------------------- #
    #  Helpers                                                               #
    # -------------------------------------------------------------------- #
    def _add_queue_row(self, uid: str, metric: str, confidence: str,
                       decision: str, text_color: str, bg_color: str):
        row = self._table.rowCount()
        self._table.insertRow(row)

        mono_font = QFont("JetBrains Mono, Consolas, monospace")

        uid_item = QTableWidgetItem(uid)
        uid_item.setFont(mono_font)
        self._table.setItem(row, 0, uid_item)
        self._table.setItem(row, 1, QTableWidgetItem(metric))
        self._table.setItem(row, 2, QTableWidgetItem(confidence))

        badge_widget = QLabel(decision)
        badge_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_widget.setStyleSheet(
            f"background-color: {bg_color}; color: {text_color}; "
            "border: none; border-radius: 4px; padding: 3px 8px; "
            "font-size: 9px; font-weight: 800;"
        )
        badge_widget.setFixedHeight(22)

        cell = QWidget()
        cell_lay = QHBoxLayout(cell)
        cell_lay.setContentsMargins(8, 4, 8, 4)
        cell_lay.addWidget(badge_widget)
        cell_lay.addStretch()
        self._table.setCellWidget(row, 3, cell)
        self._table.setRowHeight(row, 48)

    @Slot(bool)
    def set_etl_state(self, active: bool):
        if active:
            self._etl_btn.setText("ETL: ACTIVE ○ STOP")
        else:
            self._etl_btn.setText("TOGGLE ETL STATE")

    # -------------------------------------------------------------------- #
    #  Prediction                                                            #
    # -------------------------------------------------------------------- #
    def _emit_predict(self):
        try:
            val_map = {
                "glucose": float(self._inputs["glucose"].text() or 0.0),
                "age":     float(self._inputs["age"].text()     or 0.0),
                "bmi":     float(self._inputs["bmi"].text()     or 0.0),
            }
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers.")
            return

        self._run_btn.setText("PREDICTING…")
        self._run_btn.setEnabled(False)
        self.predict_requested.emit(val_map)

    @Slot(object)
    def display_prediction_result(self, result):
        self._run_btn.setText("RUN CACHED MODEL")
        self._run_btn.setEnabled(True)

        if isinstance(result, Exception):
            QMessageBox.critical(self, "Prediction Error", str(result))
            return

        res: PredictionResult = result
        score = f"{res.probability:.1%}"
        is_high = res.risk_label != "Low"

        self._score_lbl.setText(score)
        self._result_card.show()

        if is_high:
            self._result_card.setStyleSheet(
                "background: #fff1f2; border: 1px solid #fecdd3; border-radius: 12px;"
            )
            self._score_text_label.setStyleSheet(
                "font-size: 9px; font-weight: 800; color: #be123c; letter-spacing: 1px; border: none;"
            )
            self._score_lbl.setStyleSheet(
                "font-size: 18px; font-weight: 900; color: #9f1239; border: none;"
            )
            self._risk_lbl.setText("POSITIVE / HIGH RISK — REVIEW REQUIRED")
            self._risk_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 800; color: #be123c; letter-spacing: 0.5px; border: none;"
            )
        else:
            self._result_card.setStyleSheet(
                "background: #f0fdfa; border: 1px solid #99f6e4; border-radius: 12px;"
            )
            self._score_text_label.setStyleSheet(
                "font-size: 9px; font-weight: 800; color: #0f766e; letter-spacing: 1px; border: none;"
            )
            self._score_lbl.setStyleSheet(
                "font-size: 18px; font-weight: 900; color: #134e4a; border: none;"
            )
            self._risk_lbl.setText("NEGATIVE / LOW RISK BASELINE")
            self._risk_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 800; color: #0f766e; letter-spacing: 0.5px; border: none;"
            )

        # # Also add to queue table
        # decision = "ALERT RISK" if is_high else "LOW RISK"
        # text_color = "#dc2626" if is_high else "#059669"
        # bg_color   = "#fee2e2" if is_high else "#dcfce7"
        # self._add_queue_row(
        #     "#MANUAL", f"Glucose: {int(self._inputs['glucose'].text() or 0)}",
        #     f"{res.probability:.1%}", decision, text_color, bg_color
        # )
