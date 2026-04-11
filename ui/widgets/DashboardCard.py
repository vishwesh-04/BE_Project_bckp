from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal


class DashboardCard(QFrame):

    clicked = Signal()

    def __init__(self, title, value, subtext, border_color="#0d9488", link_text=""):
        super().__init__()

        self.setStyleSheet(f"""
            #DashboardCard {{
                background-color: #ffffff;
                border-left: 4px solid {border_color};
                border-radius: 8px;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setProperty("class", "CardTitle")

        self.value_lbl = QLabel(value)
        self.value_lbl.setProperty("class", "CardValue")

        sub_layout = QHBoxLayout()
        self.sub_lbl = QLabel(subtext)
        self.sub_lbl.setStyleSheet(f"color: {border_color}; font-weight: bold; font-size: 11px;")
        sub_layout.addWidget(self.sub_lbl)

        if link_text:
            link = QLabel(link_text)
            link.setProperty("class", "CardLink")
            sub_layout.addWidget(link)

        sub_layout.addStretch()

        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)
        layout.addLayout(sub_layout)

        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if widget: widget.setAttribute(Qt.WA_TransparentForMouseEvents)

    def update_content(self, title, value, border_color="#0d9488"):
        self.title_lbl.setText(title.upper())
        self.value_lbl.setText(value)
        self.setStyleSheet(f"""
            #DashboardCard {{
                background-color: #ffffff;
                border-left: 4px solid {border_color};
                border-radius: 8px;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)
        # self.sub_lbl.setStyleSheet(f"color: {border_color}; font-weight: bold; font-size: 11px;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)