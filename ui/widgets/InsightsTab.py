from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar
)
from PySide6.QtCore import Qt
from PySide6.QtCharts import QChart, QChartView, QBarSet, QHorizontalBarSeries, QBarCategoryAxis, QValueAxis
from PySide6.QtGui import QPainter, QColor

class InsightsTab(QWidget):
    def __init__(self):
        super().__init__()
        # Main layout for the whole tab
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(25)

        # 1. Header Row
        self._init_header()

        # 2. Split View (Middle)
        split_layout = QHBoxLayout()
        split_layout.setSpacing(20)
        
        # Left Side: Global Feature Impact (70% stretch)
        self.chart_card = self._create_chart_card()
        split_layout.addWidget(self.chart_card, 7)
        
        # Right Side: Local Insights & Contribution (30% stretch)
        self.local_insight_card = self._create_local_insight_card()
        split_layout.addWidget(self.local_insight_card, 3)

        self.layout.addLayout(split_layout)

        # 3. Action Row (Bottom)
        self._init_action_row()

        # Push everything to the top
        self.layout.addStretch()

    def _init_header(self):
        header_layout = QHBoxLayout()
        title = QLabel("SHAP Interpretability Dashboard")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1e293b;")
        
        # Status Badges
        badge1 = QLabel("ETL Idle")
        badge1.setStyleSheet("background-color: #f1f5f9; color: #64748b; padding: 5px 10px; border-radius: 10px; font-size: 12px; font-weight: bold;")
        
        badge2 = QLabel("Global Model Cached")
        badge2.setStyleSheet("background-color: #dcfce7; color: #166534; padding: 5px 10px; border-radius: 10px; font-size: 12px; font-weight: bold;")
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(badge1)
        header_layout.addWidget(badge2)
        
        self.layout.addLayout(header_layout)

    def _create_chart_card(self):
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("GLOBAL FEATURE IMPACT (SHAP)")
        title.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title)

        # Setup QtCharts Horizontal Bar Chart
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(False)
        chart.layout().setContentsMargins(0, 0, 0, 0)
        chart.setBackgroundRoundness(0)

        series = QHorizontalBarSeries()
        
        # Mock Data (Teal bars for SHAP values)
        set0 = QBarSet("SHAP Value")
        set0.setColor(QColor("#0d9488")) # Teal
        set0.append([0.1, 0.25, 0.4, 0.65, 0.85])
        series.append(set0)

        chart.addSeries(series)

        # Axes
        categories = ["BMI", "Age", "Blood Pressure", "Heart Rate", "Glucose"]
        axisY = QBarCategoryAxis()
        axisY.append(categories)
        chart.addAxis(axisY, Qt.AlignLeft)
        series.attachAxis(axisY)

        axisX = QValueAxis()
        axisX.setTitleText("Mean |SHAP| value (impact on model output)")
        chart.addAxis(axisX, Qt.AlignBottom)
        series.attachAxis(axisX)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setMinimumHeight(300)
        chart_view.setStyleSheet("background: transparent;")
        
        layout.addWidget(chart_view)
        return card

    def _create_local_insight_card(self):
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("INDIVIDUAL SAMPLE REASONING")
        title.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title)

        # Natural Language Insight (Soft green background)
        insight_text = (
            "<b>Local Insight #1:</b><br><br>"
            "This patient has a higher predicted risk primarily due to elevated <b>Glucose</b> levels "
            "and higher than average <b>BMI</b>. Physical activity slightly offsets this risk."
        )
        insight_label = QLabel(insight_text)
        insight_label.setWordWrap(True)
        insight_label.setStyleSheet("""
            background-color: #ecfdf5;
            color: #065f46;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #a7f3d0;
            font-size: 13px;
            line-height: 1.5;
        """)
        layout.addWidget(insight_label)

        # Typical Contribution Plot (Red/Blue Bars using QProgressBar)
        contrib_title = QLabel("Feature Contributions")
        contrib_title.setStyleSheet("color: #475569; font-size: 11px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(contrib_title)

        layout.addWidget(self._create_contribution_row("Glucose", "+0.31", True))
        layout.addWidget(self._create_contribution_row("BMI", "+0.15", True))
        layout.addWidget(self._create_contribution_row("Activity", "-0.09", False))
        
        layout.addStretch()
        return card

    def _create_contribution_row(self, feature_name, value_str, is_positive):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl = QLabel(feature_name)
        lbl.setFixedWidth(60)
        lbl.setStyleSheet("color: #475569; font-size: 12px;")
        
        val_lbl = QLabel(value_str)
        val_lbl.setFixedWidth(40)
        val_lbl.setStyleSheet(f"color: {'#e11d48' if is_positive else '#2563eb'}; font-size: 12px; font-weight: bold;")
        
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        bar.setMaximum(100)
        
        # Style progress bar based on positive (red) or negative (blue) contribution
        color = "#e11d48" if is_positive else "#2563eb"
        val_pct = 70 if is_positive else 30 # Mock percentages
        bar.setValue(val_pct)
        
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #f1f5f9;
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)
        
        row_layout.addWidget(lbl)
        row_layout.addWidget(val_lbl)
        row_layout.addWidget(bar)
        
        return row

    def _init_action_row(self):
        action_layout = QHBoxLayout()
        action_layout.setSpacing(20)

        export_btn = self._create_action_card("Export Report", "Save insights as PDF")
        history_btn = self._create_action_card("View History", "Past patient interpretations")
        contact_btn = self._create_action_card("Contact Admin", "Report anomaly in data")

        action_layout.addWidget(export_btn)
        action_layout.addWidget(history_btn)
        action_layout.addWidget(contact_btn)

        self.layout.addLayout(action_layout)

    def _create_action_card(self, title_text, desc_text):
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title = QLabel(title_text)
        title.setStyleSheet("color: #0f172a; font-size: 14px; font-weight: bold;")
        
        desc = QLabel(desc_text)
        desc.setStyleSheet("color: #64748b; font-size: 11px;")
        
        layout.addWidget(title)
        layout.addWidget(desc)
        
        return card
