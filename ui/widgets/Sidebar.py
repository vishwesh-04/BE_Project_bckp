from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton, QProgressBar, QHBoxLayout, QButtonGroup
from PySide6.QtCore import Qt


class Sidebar(QFrame):
    def __init__(self, stack):  # Added 'stack' argument to control the QStackedWidget
        super().__init__()
        self.setObjectName("Sidebar")
        self.stack = stack  # Store reference to the stack

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 25, 15, 25)

        # 1. Logo Section
        logo = QLabel("MedLink FL")
        logo.setProperty("class", "LogoText")
        layout.addWidget(logo)
        layout.addSpacing(30)

        # 2. Navigation Group
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        self.nav_items = ["Configuration", "Live Prediction", "SHAP Insights"]

        for i, name in enumerate(self.nav_items):
            btn = QPushButton(f"  {name}")
            btn.setProperty("class", "SidebarItem")
            btn.setCheckable(True)

            # CRITICAL: Add the BUTTON to the layout, not the group
            layout.addWidget(btn)

            # Add the button to the group and give it an ID that matches the stack index
            self.button_group.addButton(btn, i)

        # Connect the group clicking to the stack index switching
        self.button_group.idClicked.connect(self.stack.setCurrentIndex)

        # Set the first button as active by default
        if self.button_group.button(0):
            self.button_group.button(0).setChecked(True)

        layout.addStretch()

        # 3. System Health Section
        health_container = QVBoxLayout()
        health_title = QLabel("SYSTEM HEALTH")
        health_title.setProperty("class", "HealthLabel")
        health_container.addWidget(health_title)

        # CPU Usage
        self.cpu_bar = self._create_health_item(health_container, "CPU Usage", "24%", "#0d9488")
        # GPU Temp
        self.gpu_bar = self._create_health_item(health_container, "GPU Temp", "62°C", "#f59e0b")

        layout.addLayout(health_container)

    def _create_health_item(self, parent_layout, label, val, color):
        row = QHBoxLayout()
        l = QLabel(label)
        v = QLabel(val)
        l.setProperty("class", "HealthSub")
        v.setProperty("class", "HealthSub")
        row.addWidget(l)
        row.addStretch()
        row.addWidget(v)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(val.replace('%', '').replace('°C', '')))
        bar.setFixedHeight(4)
        bar.setTextVisible(False)
        # Note: In a professional setup, move this bar styling to your style.qss if possible
        bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; border-radius: 2px; }}")

        parent_layout.addLayout(row)
        parent_layout.addWidget(bar)
        parent_layout.addSpacing(10)
        return bar