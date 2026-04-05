from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt


class DashboardCard(QFrame):
    def __init__(self, title, value, subtext, border_color="#0d9488", link_text=""):
        super().__init__()
        self.setProperty("class", "GlassCard")
        # Inline style for the dynamic border color
        self.setStyleSheet(f"border-left: 4px solid {border_color};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title_lbl = QLabel(title.upper())
        title_lbl.setProperty("class", "CardTitle")

        value_lbl = QLabel(value)
        value_lbl.setProperty("class", "CardValue")

        sub_layout = QHBoxLayout()
        sub_lbl = QLabel(subtext)
        sub_lbl.setStyleSheet(f"color: {border_color}; font-weight: bold; font-size: 11px;")
        sub_layout.addWidget(sub_lbl)

        if link_text:
            link = QLabel(link_text)
            link.setProperty("class", "CardLink")
            sub_layout.addWidget(link)

        sub_layout.addStretch()

        layout.addWidget(title_lbl)
        layout.addWidget(value_lbl)
        layout.addLayout(sub_layout)