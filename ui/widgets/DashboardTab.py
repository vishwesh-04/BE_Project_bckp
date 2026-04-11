from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries, QValueAxis
)
from PySide6.QtGui import QPainter, QColor, QPen


class DashboardTab(QWidget):
    """
    Tab 0 — Dashboard
    Matches the HTML prototype 'dashboard' section:
      - 4 metric cards (Training Round, Validation Acc, Dataset Size, FL Strategy)
      - Local Training Metrics line chart (accuracy over rounds)
      - Environment Quick-View panel (SecAgg+, DP, Warehouse, Log Level)
    """

    # Emitted when the user clicks "Edit Configuration" in the env panel
    goto_settings_requested = Signal()
    # Emitted when the user clicks the Training Round card (open logs)
    open_logs_requested = Signal()

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(20)

        # ── Row 1: Metric Cards ───────────────────────────────────────────
        root.addLayout(self._build_metric_row())

        # ── Row 2: Chart (left) + Env panel (right) ──────────────────────
        split = QHBoxLayout()
        split.setSpacing(20)
        split.addWidget(self._build_chart_card(), stretch=1)
        split.addWidget(self._build_env_card(), stretch=1)
        root.addLayout(split)

        root.addStretch()

    # -------------------------------------------------------------------- #
    #  Metric row                                                           #
    # -------------------------------------------------------------------- #
    def _build_metric_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(20)

        cards = [
            ("Training Round",  "14",       "COMPLETED",                "#0d9488", True),
            ("Validation Acc.", "84.12%",   "↑ 1.2% from Round 13",     "#3b82f6", False),
            ("Dataset Size",    "12,402",   "Local Warehouse Entries",   "#f59e0b", False),
            ("FL Strategy",     "FedAvg",   "Managed by Server",         "#6366f1", False),
        ]

        for title, value, sub, color, clickable in cards:
            card = self._make_stat_card(title, value, sub, color, clickable)
            row.addWidget(card)

        return row

    def _make_stat_card(self, title: str, value: str, sub: str,
                        border_color: str, clickable: bool) -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")
        # card.setStyleSheet(f"border-left: 4px solid {border_color};")
        if clickable:
            card.setCursor(Qt.PointingHandCursor)
            # Store ref so we can update it later
            self._round_card = card

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        lbl_title = QLabel(title.upper())
        lbl_title.setProperty("class", "CardTitle")

        lbl_value = QLabel(value)
        lbl_value.setProperty("class", "CardValue")

        lbl_sub = QLabel(sub)
        lbl_sub.setStyleSheet(f"color: {border_color}; font-size: 10px; font-weight: bold;")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)
        layout.addWidget(lbl_sub)

        # Forward click to signal if clickable
        if clickable:
            card.mousePressEvent = lambda _e: self.open_logs_requested.emit()

        return card

    # -------------------------------------------------------------------- #
    #  Line chart card                                                      #
    # -------------------------------------------------------------------- #
    def _build_chart_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)

        title = QLabel("LOCAL TRAINING METRICS")
        title.setProperty("class", "CardTitle")
        card_layout.addWidget(title)

        # Build chart
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(False)
        chart.layout().setContentsMargins(0, 0, 0, 0)
        chart.setBackgroundRoundness(0)
        chart.setBackgroundBrush(QColor("transparent"))

        # Local node accuracy (teal solid line)
        local_series = QLineSeries()
        local_series.setName("Local Node Accuracy")
        local_pts = [(8, 78), (9, 79), (10, 81.5), (11, 80.2), (12, 82.1), (13, 82.9), (14, 84.12)]
        for x, y in local_pts:
            local_series.append(x, y)
        pen = QPen(QColor("#0d9488"))
        pen.setWidth(3)
        local_series.setPen(pen)

        # Global baseline (slate dashed line)
        global_series = QLineSeries()
        global_series.setName("Global Baseline")
        global_pts = [(8, 75), (9, 76), (10, 78), (11, 79.5), (12, 81), (13, 82), (14, 83.5)]
        for x, y in global_pts:
            global_series.append(x, y)
        dash_pen = QPen(QColor("#94a3b8"))
        dash_pen.setWidth(2)
        dash_pen.setStyle(Qt.DashLine)
        global_series.setPen(dash_pen)

        chart.addSeries(local_series)
        chart.addSeries(global_series)

        axis_x = QValueAxis()
        axis_x.setRange(8, 14)
        axis_x.setTickCount(7)
        axis_x.setLabelFormat("R%d")
        axis_x.setGridLineVisible(False)

        axis_y = QValueAxis()
        axis_y.setRange(72, 90)
        axis_y.setLabelFormat("%.0f%%")
        axis_y.setGridLineColor(QColor("#f1f5f9"))

        chart.addAxis(axis_x, Qt.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignLeft)
        local_series.attachAxis(axis_x)
        local_series.attachAxis(axis_y)
        global_series.attachAxis(axis_x)
        global_series.attachAxis(axis_y)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setMinimumHeight(220)
        chart_view.setStyleSheet("background: transparent;")
        chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout.addWidget(chart_view)
        return card

    # -------------------------------------------------------------------- #
    #  Environment quick-view card                                          #
    # -------------------------------------------------------------------- #
    def _build_env_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("ENVIRONMENT QUICK-VIEW")
        title.setProperty("class", "CardTitle")
        layout.addWidget(title)

        env_items = [
            ("SecAgg+ Status",       "ENABLED",    "#0d9488"),
            ("Differential Privacy", "DISABLED",   "#94a3b8"),
            ("Warehouse Sync",       "CONNECTED",  "#0d9488"),
            ("Log Level",            "INFO",        "#334155"),
        ]

        for label_text, val_text, val_color in env_items:
            row = QFrame()
            row.setStyleSheet("background: #f8fafc; border-radius: 8px;")
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(12, 10, 12, 10)

            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 500;")

            val = QLabel(val_text)
            val.setStyleSheet(f"color: {val_color}; font-size: 11px; font-weight: bold;")

            row_lay.addWidget(lbl)
            row_lay.addStretch()
            row_lay.addWidget(val)
            layout.addWidget(row)

        layout.addStretch()

        # "Edit Configuration" button → pings goto_settings_requested signal
        edit_btn = QPushButton("EDIT CONFIGURATION")
        edit_btn.setProperty("class", "SecondaryButton")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setFixedHeight(36)
        edit_btn.clicked.connect(self.goto_settings_requested.emit)
        layout.addWidget(edit_btn)

        return card

    # -------------------------------------------------------------------- #
    #  Public update slots (called from main or controller)                 #
    # -------------------------------------------------------------------- #
    @Slot(int)
    def update_round(self, round_num: int):
        """Update the training round card's value."""
        # Future: update the round number dynamically
        pass
