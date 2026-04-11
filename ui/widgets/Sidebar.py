from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QButtonGroup
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QByteArray


# SVG path strings for each nav item (all 18×18 viewBox)
_ICONS = {
    "Dashboard": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect width="7" height="9" x="3" y="3" rx="1"/>
        <rect width="7" height="5" x="14" y="3" rx="1"/>
        <rect width="7" height="9" x="14" y="12" rx="1"/>
        <rect width="7" height="5" x="3" y="16" rx="1"/>
    </svg>""",

    "Live Prediction": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
    </svg>""",

    "SHAP Insights": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="20" x2="18" y2="10"/>
        <line x1="12" y1="20" x2="12" y2="4"/>
        <line x1="6" y1="20" x2="6" y2="14"/>
    </svg>""",

    "Round History": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
        <path d="M3 3v5h5"/>
        <path d="M12 7v5l4 2"/>
    </svg>""",

    "Node Settings": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
        <circle cx="12" cy="12" r="3"/>
    </svg>""",
}


class Sidebar(QFrame):
    """
    Sidebar navigation with 5 tabs and SVG icons.
    Emits nav_clicked(index) when a tab button is clicked.
    Maps: 0=Dashboard, 1=Live Prediction, 2=SHAP Insights, 3=Round History, 4=Node Settings
    """
    nav_clicked = Signal(int)

    # Tab ordering must match QStackedWidget order in main.py
    NAV_ITEMS = [
        "Dashboard",
        "Live Prediction",
        "SHAP Insights",
        "Round History",
        "Node Settings",
    ]

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Logo section ─────────────────────────────────────────────────
        logo_frame = QFrame()
        logo_frame.setStyleSheet(
            "background: white; border-bottom: 1px solid #f1f5f9; padding: 0;"
        )
        logo_layout = QHBoxLayout(logo_frame)
        logo_layout.setContentsMargins(20, 18, 20, 18)
        logo_layout.setSpacing(12)

        # Teal icon capsule
        icon_lbl = QLabel("♥")  # Unicode heart as fallback
        icon_lbl.setStyleSheet(
            "background: #0d9488; color: white; border-radius: 8px; "
            "padding: 6px; font-size: 14px; font-weight: bold;"
        )
        icon_lbl.setFixedSize(34, 34)
        icon_lbl.setAlignment(Qt.AlignCenter)

        name_layout = QVBoxLayout()
        name_layout.setSpacing(0)
        name_layout.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel("MedLink")
        name_label.setProperty("class", "LogoText")

        node_label = QLabel("FL Node Pro")
        node_label.setStyleSheet(
            "color: #0d9488; font-size: 9px; font-weight: 800; "
            "letter-spacing: 2px; text-transform: uppercase;"
        )

        name_layout.addWidget(name_label)
        name_layout.addWidget(node_label)

        logo_layout.addWidget(icon_lbl)
        logo_layout.addLayout(name_layout)
        logo_layout.addStretch()

        layout.addWidget(logo_frame)

        # ── Navigation ───────────────────────────────────────────────────
        nav_frame = QFrame()
        nav_frame.setStyleSheet("background: white;")
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(12, 16, 12, 16)
        nav_layout.setSpacing(4)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        for i, name in enumerate(self.NAV_ITEMS):
            # Insert a section divider before "Node Settings"
            if name == "Node Settings":
                divider_lbl = QLabel("SYSTEM")
                divider_lbl.setStyleSheet(
                    "color: #94a3b8; font-size: 9px; font-weight: 800; "
                    "letter-spacing: 2px; padding: 14px 4px 4px 4px; "
                    "background: transparent;"
                )
                nav_layout.addWidget(divider_lbl)

            btn = QPushButton(f"   {name}")
            btn.setProperty("class", "SidebarItem")
            btn.setCheckable(True)
            btn.setFixedHeight(42)
            btn.setCursor(Qt.PointingHandCursor)

            nav_layout.addWidget(btn)
            self.button_group.addButton(btn, i)

        # Wire group signal → our public signal
        self.button_group.idClicked.connect(self.nav_clicked.emit)

        # Default: first button active
        if self.button_group.button(0):
            self.button_group.button(0).setChecked(True)

        layout.addWidget(nav_frame)
        layout.addStretch()

        # ── Resource Load section ─────────────────────────────────────────
        health_frame = QFrame()
        health_frame.setStyleSheet(
            "background: #f8fafc; border-top: 1px solid #f1f5f9;"
        )
        health_layout = QVBoxLayout(health_frame)
        health_layout.setContentsMargins(16, 14, 16, 16)
        health_layout.setSpacing(10)

        health_title = QLabel("RESOURCE LOAD")
        health_title.setProperty("class", "HealthLabel")
        health_layout.addWidget(health_title)

        self.gpu_bar = self._create_health_item(health_layout, "Local GPU", "58%", "#0d9488")
        self.mem_bar = self._create_health_item(health_layout, "Memory",    "4.2 GB", "#3b82f6")

        layout.addWidget(health_frame)

    # ------------------------------------------------------------------ #
    #  Health bar helper                                                   #
    # ------------------------------------------------------------------ #
    def _create_health_item(self, parent_layout, label, val, color):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        l = QLabel(label)
        v = QLabel(val)
        l.setProperty("class", "HealthSub")
        v.setProperty("class", "HealthSub")
        row.addWidget(l)
        row.addStretch()
        row.addWidget(v)

        bar = QProgressBar()
        bar.setRange(0, 100)
        # Parse numeric value for the bar
        numeric = val.replace('%', '').replace(' GB', '').strip()
        try:
            bar.setValue(int(float(numeric) * (100 / 8) if 'GB' in val else float(numeric)))
        except ValueError:
            bar.setValue(0)
        bar.setFixedHeight(4)
        bar.setTextVisible(False)
        bar.setStyleSheet(
            f"QProgressBar {{ background:#e2e8f0; border:none; border-radius:2px; }}"
            f"QProgressBar::chunk {{ background:{color}; border-radius:2px; }}"
        )

        parent_layout.addLayout(row)
        parent_layout.addWidget(bar)

        return bar

    # ------------------------------------------------------------------ #
    #  Public helper                                                        #
    # ------------------------------------------------------------------ #
    def set_active_tab(self, index: int):
        """Programmatically activate a tab button (e.g. from 'Edit Config' link)."""
        btn = self.button_group.button(index)
        if btn:
            btn.setChecked(True)