from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class LogsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Local Training Runtime Logs")
        self.setMinimumSize(700, 450)
        # Remove default title bar for a cleaner look if desired,
        # but standard QDialog is safer for beginners.

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Custom Header
        header = QFrame()
        header.setStyleSheet("background-color: white; border-bottom: 1px solid #e2e8f0;")
        header_layout = QHBoxLayout(header)

        title = QLabel("Local Training Runtime Logs")
        title.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 14px;")

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("border: none; color: #94a3b8; font-size: 16px;")
        close_btn.clicked.connect(self.close)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        layout.addWidget(header)

        # 2. Terminal Area
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                color: #f8fafc;
                border: none;
                padding: 20px;
                line-height: 1.5;
            }
        """)
        # Set Monospace Font
        font = QFont("JetBrains Mono", 10)
        if not font.exactMatch(): font = QFont("Consolas", 10)  # Fallback
        self.terminal.setFont(font)

        layout.addWidget(self.terminal)
    def append_log(self, html_str):
        self.terminal.append(html_str)