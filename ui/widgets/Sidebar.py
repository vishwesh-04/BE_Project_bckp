from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, QByteArray, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer


# ─────────────────────────────────────────────────────────────────────────────
# SVG icon strings  (18×18 viewBox — match prototype exactly)
# ─────────────────────────────────────────────────────────────────────────────
def _svg(path_data: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" '
        f'viewBox="0 0 24 24" fill="none" stroke="COLOR" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f'{path_data}</svg>'
    )


_SVG_ICONS: dict[str, str] = {
    "Dashboard": _svg(
        '<rect width="7" height="9" x="3" y="3" rx="1"/>'
        '<rect width="7" height="5" x="14" y="3" rx="1"/>'
        '<rect width="7" height="9" x="14" y="12" rx="1"/>'
        '<rect width="7" height="5" x="3" y="16" rx="1"/>'
    ),
    "Live Prediction": _svg(
        '<path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'
    ),
    "SHAP Insights": _svg(
        '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8'
        'a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>'
        '<polyline points="7.5 4.21 12 6.81 16.5 4.21"/>'
        '<polyline points="7.5 19.79 7.5 14.6 3 12"/>'
        '<polyline points="21 12 16.5 14.6 16.5 19.79"/>'
        '<polyline points="3.27 6.96 12 12.01 20.73 6.96"/>'
        '<line x1="12" y1="22.08" x2="12" y2="12"/>'
    ),
    "Round History": _svg(
        '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>'
        '<path d="M3 3v5h5"/>'
        '<path d="M12 7v5l4 2"/>'
    ),
    "Node Settings": _svg(
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 '
        '0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 '
        '1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73'
        'l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 '
        '2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73'
        'l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74'
        'l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 '
        '0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
}


def _svg_to_icon(svg_str: str, color: str = "#475569") -> QIcon:
    """Render an SVG string to a QIcon at 18×18 with the given stroke color."""
    colored = svg_str.replace("COLOR", color)
    renderer = QSvgRenderer(QByteArray(colored.encode()))
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


# ─────────────────────────────────────────────────────────────────────────────

class Sidebar(QFrame):
    """
    Sidebar navigation with 5 tabs and SVG icons.
    Emits nav_clicked(index) when a tab button is clicked.
    Maps: 0=Dashboard, 1=Live Prediction, 2=SHAP Insights, 3=Round History, 4=Node Settings
    """

    nav_clicked = Signal(int)

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
        layout.addWidget(self._build_logo())

        # ── Navigation ───────────────────────────────────────────────────
        nav_frame = QFrame()
        nav_frame.setStyleSheet("background: white;")
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(12, 16, 12, 16)
        nav_layout.setSpacing(2)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        for i, name in enumerate(self.NAV_ITEMS):
            if name == "Node Settings":
                divider = QLabel("SYSTEM")
                divider.setStyleSheet(
                    "color: #94a3b8; font-size: 9px; font-weight: 800; "
                    "letter-spacing: 2px; padding: 14px 4px 4px 4px; "
                    "background: transparent;"
                )
                nav_layout.addWidget(divider)

            btn = self._nav_button(name, i)
            nav_layout.addWidget(btn)
            self.button_group.addButton(btn, i)

        self.button_group.idClicked.connect(self.nav_clicked.emit)

        if self.button_group.button(0):
            self.button_group.button(0).setChecked(True)

        layout.addWidget(nav_frame)
        layout.addStretch()

        # ── Resource Load section ─────────────────────────────────────────
        layout.addWidget(self._build_resource_frame())

    # ------------------------------------------------------------------ #

    def _build_logo(self) -> QFrame:
        logo_frame = QFrame()
        logo_frame.setStyleSheet(
            "background: white; border-bottom: 1px solid #f1f5f9; padding: 0;"
        )
        lay = QHBoxLayout(logo_frame)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        # Teal icon capsule — ECG waveform symbol
        icon_lbl = QLabel("⚕")
        icon_lbl.setStyleSheet(
            "background: #0d9488; color: white; border-radius: 8px; "
            "padding: 4px; font-size: 16px; font-weight: bold;"
        )
        icon_lbl.setFixedSize(34, 34)
        icon_lbl.setAlignment(Qt.AlignCenter)

        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        name_col.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel("MedLink")
        name_label.setStyleSheet(
            "font-size: 17px; font-weight: 800; color: #0f172a; "
            "letter-spacing: -0.5px; background: transparent;"
        )

        node_label = QLabel("FL Node Pro")
        node_label.setStyleSheet(
            "color: #0d9488; font-size: 9px; font-weight: 800; "
            "letter-spacing: 2px; background: transparent;"
        )

        name_col.addWidget(name_label)
        name_col.addWidget(node_label)

        lay.addWidget(icon_lbl)
        lay.addLayout(name_col)
        lay.addStretch()

        return logo_frame

    def _nav_button(self, name: str, index: int) -> QPushButton:
        """Build a sidebar nav button with an SVG icon on the left."""
        btn = QPushButton(f"  {name}")
        btn.setProperty("class", "SidebarItem")
        btn.setCheckable(True)
        btn.setFixedHeight(42)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setIconSize(QSize(18, 18))

        # Default (inactive) icon — slate color
        inactive_icon = _svg_to_icon(_SVG_ICONS.get(name, ""), color="#475569")
        active_icon   = _svg_to_icon(_SVG_ICONS.get(name, ""), color="white")

        btn.setIcon(inactive_icon)

        # Swap icon color when checked state changes
        original_toggled = None

        def _on_toggle(checked, b=btn, ai=active_icon, ii=inactive_icon):
            if checked:
                b.setIcon(ai)
                b.setStyleSheet("background-color: #0d9488;")
            else:
                b.setIcon(ii)
                b.setStyleSheet("background-color: white;")
            
                

        btn.toggled.connect(_on_toggle)

        return btn

    def _build_resource_frame(self) -> QFrame:
        health_frame = QFrame()
        health_frame.setStyleSheet(
            "background: #f8fafc; border-top: 1px solid #f1f5f9;"
        )
        lay = QVBoxLayout(health_frame)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        title = QLabel("RESOURCE LOAD")
        title.setStyleSheet(
            "color: #94a3b8; font-size: 9px; font-weight: 800; "
            "letter-spacing: 2px; background: transparent;"
        )
        lay.addWidget(title)

        self.gpu_bar = self._resource_item(lay, "Local GPU", "58%",   "#0d9488", 58)
        self.mem_bar = self._resource_item(lay, "Memory",    "4.2 GB", "#3b82f6", 52)

        return health_frame

    @staticmethod
    def _resource_item(parent_layout, label: str, val: str, color: str, pct: int) -> QProgressBar:
        row = QHBoxLayout()
        lbl = QLabel(label)
        val_lbl = QLabel(val)
        for l in (lbl, val_lbl):
            l.setStyleSheet(
                "color: #64748b; font-size: 9px; font-weight: 700; "
                "letter-spacing: 0.5px; background: transparent;"
            )
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val_lbl)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(pct)
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
    #  Public helpers                                                       #
    # ------------------------------------------------------------------ #
    def set_active_tab(self, index: int):
        """Programmatically activate a tab button."""
        btn = self.button_group.button(index)
        if btn:
            btn.setChecked(True)