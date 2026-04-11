from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
)
from PySide6.QtCore import Qt
from PySide6.QtCharts import (
    QChart, QChartView, QBarSet, QHorizontalBarSeries, QBarCategoryAxis, QValueAxis
)
from PySide6.QtGui import QPainter, QColor


class InsightsTab(QWidget):
    """
    Tab 2 — SHAP Insights
    Matches the HTML prototype 'insights' section:
      - Left 2/3: Global SHAP Feature Importance horizontal bar chart
      - Right 1/3: Local Explainability card with:
          - Primary Driver text block
          - Sample SHAP Breakdown (3 progress bars: Glucose, BMI, Activity)
          - Export SHAP Report button
    """

    def __init__(self):
        super().__init__()

        root = QHBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(20)

        # Left 2/3: Global SHAP chart card
        root.addWidget(self._build_chart_card(), stretch=2)

        # Right 1/3: Local Explainability card
        root.addWidget(self._build_local_card(), stretch=1)

    # -------------------------------------------------------------------- #
    #  Left card — Global SHAP Feature Importance                           #
    # -------------------------------------------------------------------- #
    def _build_chart_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("GLOBAL SHAP FEATURE IMPORTANCE")
        title.setProperty("class", "CardTitle")
        layout.addWidget(title)

        # Horizontal bar chart — matches prototype data
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(False)
        chart.layout().setContentsMargins(0, 0, 0, 0)
        chart.setBackgroundRoundness(0)
        chart.setBackgroundBrush(QColor("transparent"))

        bar_set = QBarSet("Impact")
        bar_set.setColor(QColor("#0d9488"))
        # Prototype data: Glucose, Age, BMI, Insulin, BP, Pedigree
        values = [0.45, 0.38, 0.29, 0.21, 0.18, 0.12]
        for v in values:
            bar_set.append(v)

        series = QHorizontalBarSeries()
        series.append(bar_set)
        chart.addSeries(series)

        categories = ["Pedigree", "Blood Pressure", "Insulin", "BMI", "Age", "Glucose"]
        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setLabelsFont(self.font())
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        axis_x = QValueAxis()
        axis_x.setRange(0, 0.55)
        axis_x.setLabelFormat("%.2f")
        axis_x.setGridLineColor(QColor("#f1f5f9"))
        axis_x.setTickCount(6)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setMinimumHeight(280)
        chart_view.setStyleSheet("background: transparent;")

        layout.addWidget(chart_view)
        return card

    # -------------------------------------------------------------------- #
    #  Right card — Local Explainability                                     #
    # -------------------------------------------------------------------- #
    def _build_local_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("LOCAL EXPLAINABILITY")
        title.setProperty("class", "CardTitle")
        layout.addWidget(title)

        # Primary Driver text box
        driver_box = QFrame()
        driver_box.setStyleSheet(
            "background: #f8fafc; border: 1px solid #f1f5f9; border-radius: 10px;"
        )
        driver_lay = QVBoxLayout(driver_box)
        driver_lay.setContentsMargins(12, 10, 12, 10)

        driver_lbl_title = QLabel("PRIMARY DRIVER")
        driver_lbl_title.setProperty("class", "CardTitle")

        driver_text = QLabel(
            "In your facility, <b>Age Factor</b> has a 12% higher impact on "
            "predictions than the global average."
        )
        driver_text.setWordWrap(True)
        driver_text.setStyleSheet(
            "color: #334155; font-size: 11px; font-weight: 500; line-height: 1.4;"
        )
        driver_text.setTextFormat(Qt.RichText)

        driver_lay.addWidget(driver_lbl_title)
        driver_lay.addWidget(driver_text)
        layout.addWidget(driver_box)

        # Divider label
        breakdown_lbl = QLabel("SAMPLE SHAP BREAKDOWN")
        breakdown_lbl.setProperty("class", "CardTitle")
        breakdown_lbl.setStyleSheet(
            "color: #94a3b8; font-size: 9px; font-weight: 800; "
            "letter-spacing: 2px; padding-top: 8px; border-top: 1px solid #f1f5f9;"
        )
        layout.addWidget(breakdown_lbl)

        # SHAP bars matching prototype
        layout.addWidget(self._shap_bar("Glucose",  "+0.34", 0.75,  positive=True))
        layout.addWidget(self._shap_bar("BMI",      "+0.12", 0.25,  positive=True))
        layout.addWidget(self._shap_bar("Activity", "-0.18", 0.40,  positive=False))

        layout.addStretch()

        # Export SHAP Report button
        export_btn = QPushButton("EXPORT SHAP REPORT")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setFixedHeight(36)
        export_btn.setStyleSheet(
            "background-color: #0d9488; color: white; font-weight: 800; "
            "font-size: 10px; letter-spacing: 1px; border-radius: 8px; border: none;"
        )
        layout.addWidget(export_btn)

        return card

    # -------------------------------------------------------------------- #
    #  SHAP bar row helper                                                   #
    # -------------------------------------------------------------------- #
    def _shap_bar(self, name: str, value_str: str, fill: float, positive: bool) -> QWidget:
        """
        Renders a single SHAP bar row:
          [label]  [bar fill]  [+/-value]
        Positive = red (#f87171), Negative = blue (#60a5fa) — matches prototype.
        """
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(8)

        bar_color = "#f87171" if positive else "#60a5fa"
        text_color = "#ef4444" if positive else "#3b82f6"

        name_lbl = QLabel(name)
        name_lbl.setFixedWidth(58)
        name_lbl.setStyleSheet("font-size: 10px; color: #475569;")

        # Bar track
        track = QFrame()
        track.setFixedHeight(8)
        track.setStyleSheet(
            "background: #f1f5f9; border-radius: 4px;"
        )

        # Fill bar (inner frame, width as proportion of track via stretch doesn't work
        # precisely in Qt; we use a nested layout trick)
        fill_container = QFrame()
        fill_container.setFixedHeight(8)
        fill_layout = QHBoxLayout(fill_container)
        fill_layout.setContentsMargins(0, 0, 0, 0)
        fill_layout.setSpacing(0)

        fill_bar = QFrame()
        fill_bar.setFixedHeight(8)
        fill_bar.setStyleSheet(
            f"background: {bar_color}; border-radius: 4px;"
        )

        fill_int = max(1, int(fill * 100))
        fill_layout.addWidget(fill_bar, stretch=fill_int)
        fill_layout.addStretch(100 - fill_int)

        val_lbl = QLabel(value_str)
        val_lbl.setFixedWidth(36)
        val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        val_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 800; color: {text_color};"
        )

        lay.addWidget(name_lbl)
        lay.addWidget(fill_container, stretch=1)
        lay.addWidget(val_lbl)

        return row
