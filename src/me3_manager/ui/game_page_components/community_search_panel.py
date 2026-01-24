"""
Community search results UI components.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from me3_manager.services.community_service import CommunityProfile
from me3_manager.utils.platform_utils import PlatformUtils
from me3_manager.utils.translator import tr


class ImageLoader(QThread):
    finished = Signal(QPixmap)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            import requests

            resp = requests.get(self.url, timeout=10)
            if resp.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(resp.content)
                self.finished.emit(pixmap)
        except Exception:
            pass


class CommunityResultCard(QWidget):
    install_requested = Signal(object)  # CommunityProfile

    def __init__(self, profile: CommunityProfile):
        super().__init__()
        self.profile = profile
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build()
        if self.profile.image_url:
            self._load_image()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.install_requested.emit(self.profile)
        super().mousePressEvent(event)

    def _load_image(self):
        self.loader = ImageLoader(self.profile.image_url)
        self.loader.finished.connect(self._on_image_loaded)
        self.loader.start()

    def _on_image_loaded(self, pixmap: QPixmap):
        if not pixmap.isNull():
            # Scale to fit icon size
            scaled = pixmap.scaled(
                24,
                24,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.icon_label.setPixmap(scaled)
            self.icon_label.setScaledContents(True)
            self.icon_label.setText("")

    def _build(self):
        self.setFixedHeight(88)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("card")
        self.setStyleSheet(
            """
            #card {
                background-color: #252525;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
            #card:hover {
                background-color: #2d2d2d;
                border-color: #0078d4;
            }
            QLabel { background: transparent; border: none; }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        # 1. Header (Icon + Title)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        # Icon
        self.icon_label = QLabel("ME3")
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setStyleSheet(
            """
            background-color: #333333;
            color: #888888;
            font-weight: bold;
            font-size: 9px;
            border-radius: 4px;
            border: 1px solid #444;
            """
        )
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.icon_label)

        # Name
        name_clean = self.profile.name.replace(".me3", "").replace("_", " ")
        name_label = QLabel(name_clean)
        # Handle long names with ellipsis
        name_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(name_label, 1)  # Expand

        layout.addLayout(header_layout)

        # 2. Description (Compact)
        desc_label = QLabel(self.profile.description or tr("no_description"))
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Limit lines? CSS can't do it easily, but fixed height + overflow clip acts like it.
        desc_label.setStyleSheet("color: #aaaaaa; font-size: 10px; line-height: 1.1;")
        layout.addWidget(desc_label, 1)


class CommunitySearchPanel(QWidget):
    install_requested = Signal(object)  # CommunityProfile

    def __init__(self):
        super().__init__()
        self._profiles: list[CommunityProfile] = []
        self._build()

    def _build(self):
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        # Header Row
        header_layout = QHBoxLayout()
        header = QLabel(tr("community_results_header", default="Community Results"))
        header.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 600;")
        header_layout.addWidget(header)
        header_layout.addStretch()

        # Contribute Button
        contrib_btn = QPushButton(tr("community_contribute_button"))
        contrib_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        contrib_btn.clicked.connect(
            lambda: PlatformUtils.open_url(
                "https://github.com/me3-manager/me3-profiles"
            )
        )
        contrib_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #0078d4;
                border: 1px solid #0078d4;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(0, 120, 212, 0.1);
            }
            """
        )
        header_layout.addWidget(contrib_btn)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888888; font-size: 12px;")
        header_layout.addWidget(self.status)

        root.addLayout(header_layout)

        # Scroll Area for Grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                border: none;
                background: #1e1e1e;
                width: 8px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #3d3d3d;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        root.addWidget(self.scroll, 1)

        self.inner = QWidget()
        self.inner.setStyleSheet("background: transparent;")
        # Use GridLayout for cards
        self.grid_layout = QGridLayout(self.inner)
        self.grid_layout.setContentsMargins(4, 4, 16, 16)  # Right margin for scrollbar
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.scroll.setWidget(self.inner)

    def set_status(self, text: str):
        self.status.setText(text)

    def clear_results(self):
        self._profiles = []
        # Clear grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self.status.setText(tr("community_results_empty"))

    def set_results(self, profiles: list[CommunityProfile]):
        self.clear_results()
        self._profiles = profiles
        if not profiles:
            return

        # Simple responsive-ish grid: 4 columns
        cols = 4
        for i, p in enumerate(profiles):
            card = CommunityResultCard(p)
            card.install_requested.connect(self.install_requested.emit)
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(card, row, col)

        self.status.setText(tr("community_results_found", count=len(profiles)))
