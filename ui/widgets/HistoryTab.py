from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from typing import List, Dict


class HistoryTab(QWidget):
    """
    Tab 3 — Round History
    Matches the HTML prototype 'history' section:
      - A scrollable list of training rounds
      - Each row: round number | accuracy | time taken | status badge | log button
    """

    # Emitted when user clicks the Logs button for a specific round
    open_logs_requested = Signal(int)   # round_number

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(20)

        # ── Outer card ────────────────────────────────────────────────────
        outer_card = QFrame()
        outer_card.setObjectName("GlassCard")
        outer_card.setProperty("class", "GlassCard")
        outer_layout = QVBoxLayout(outer_card)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Card header
        header = QFrame()
        header.setStyleSheet(
            "background: white; border-bottom: 1px solid #f1f5f9;"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 16, 20, 16)

        h_title = QLabel("FEDERATED TRAINING ROUND LOG")
        h_title.setProperty("class", "CardTitle")
        h_layout.addWidget(h_title)
        outer_layout.addWidget(header)

        # Scrollable list area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: white;")

        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: white;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)

        # Pre-populate with mock data matching the prototype
        mock_rounds: List[Dict] = [
            {
                "round": 14,
                "accuracy": 84.12,
                "time_ago": "42m ago",
                "runtime_s": 422,
                "status": "Aggregated",
                "status_color": "#059669",
                "status_bg": "#dcfce7",
            },
            {
                "round": 13,
                "accuracy": 82.90,
                "time_ago": "4h ago",
                "runtime_s": 430,
                "status": "Aggregated",
                "status_color": "#059669",
                "status_bg": "#dcfce7",
            },
            {
                "round": 12,
                "accuracy": 82.10,
                "time_ago": "8h ago",
                "runtime_s": 415,
                "status": "Aggregated",
                "status_color": "#059669",
                "status_bg": "#dcfce7",
            },
            {
                "round": 11,
                "accuracy": 80.20,
                "time_ago": "12h ago",
                "runtime_s": 441,
                "status": "Skipped",
                "status_color": "#d97706",
                "status_bg": "#fef3c7",
            },
        ]

        for rd in mock_rounds:
            self._list_layout.addWidget(self._make_round_row(rd))

        self._list_layout.addStretch()
        scroll.setWidget(self._list_container)
        outer_layout.addWidget(scroll)

        root.addWidget(outer_card)
        root.addStretch()

    # -------------------------------------------------------------------- #
    #  Row builder                                                          #
    # -------------------------------------------------------------------- #
    def _make_round_row(self, data: Dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet("""
            QFrame {
                border: none;
                border-bottom: 1px solid #f8fafc;
                background: white;
            }
            QFrame:hover {
                background: #f8fafc;
            }
        """)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)

        # Round number column
        round_col = QFrame()
        round_col.setStyleSheet("border: none; background: transparent;")
        round_col.setFixedWidth(70)
        rc_lay = QVBoxLayout(round_col)
        rc_lay.setContentsMargins(0, 0, 0, 0)
        rc_lay.setSpacing(0)

        round_label_title = QLabel("ROUND")
        round_label_title.setStyleSheet(
            "color: #94a3b8; font-size: 9px; font-weight: bold; background: transparent;"
        )
        round_label_num = QLabel(str(data["round"]))
        round_label_num.setStyleSheet(
            "color: #0f172a; font-size: 22px; font-weight: 900; background: transparent; line-height: 1;"
        )

        rc_lay.addWidget(round_label_title)
        rc_lay.addWidget(round_label_num)
        layout.addWidget(round_col)

        # Divider
        div = QFrame()
        div.setFixedWidth(1)
        div.setFixedHeight(40)
        div.setStyleSheet("background: #f1f5f9; border: none;")
        layout.addWidget(div)
        layout.addSpacing(20)

        # Info column
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        acc_lbl = QLabel(
            f"Final Local Accuracy: <b>{data['accuracy']:.2f}%</b>"
        )
        acc_lbl.setStyleSheet("color: #1e293b; font-size: 12px; background: transparent;")

        time_lbl = QLabel(
            f"Completed {data['time_ago']} · Runtime: {data['runtime_s']}s"
        )
        time_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; background: transparent;")

        info_col.addWidget(acc_lbl)
        info_col.addWidget(time_lbl)
        layout.addLayout(info_col)
        layout.addStretch()

        # Status badge
        badge = QLabel(data["status"].upper())
        badge.setStyleSheet(f"""
            background-color: {data['status_bg']};
            color: {data['status_color']};
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 9px;
            font-weight: bold;
            border: none;
        """)
        layout.addWidget(badge)
        layout.addSpacing(16)

        # Log button
        round_num = data["round"]
        log_btn = QPushButton("↗")
        log_btn.setFixedSize(32, 32)
        log_btn.setToolTip(f"View logs for Round {round_num}")
        log_btn.setCursor(Qt.PointingHandCursor)
        log_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                color: #94a3b8;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #0d9488;
                border-color: #0d9488;
            }
        """)
        log_btn.clicked.connect(lambda _checked, r=round_num: self.open_logs_requested.emit(r))
        layout.addWidget(log_btn)

        return row

    # -------------------------------------------------------------------- #
    #  Public API                                                           #
    # -------------------------------------------------------------------- #
    def prepend_round(self, round_num: int, accuracy: float, runtime_s: int):
        """Called by the controller after a round completes to add a live entry."""
        data = {
            "round": round_num,
            "accuracy": accuracy,
            "time_ago": "just now",
            "runtime_s": runtime_s,
            "status": "Aggregated",
            "status_color": "#059669",
            "status_bg": "#dcfce7",
        }
        # Insert at position 0 (before stretch)
        self._list_layout.insertWidget(0, self._make_round_row(data))
