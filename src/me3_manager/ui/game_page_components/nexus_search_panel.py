"""
Nexus search results UI components.

Search is intentionally limited to:
- Nexus mod ID
- Nexus mod URL

This matches the product requirement and avoids API-heavy scraping/search patterns.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from me3_manager.services.nexus_service import NexusMod
from me3_manager.utils.translator import tr


@dataclass(frozen=True)
class NexusResult:
    mod: NexusMod


class NexusResultCard(QWidget):
    selected = Signal(object)  # NexusResult
    download_requested = Signal(object)  # NexusResult

    def __init__(
        self,
        result: NexusResult,
        *,
        thumbnail_loader: Callable[[str], QPixmap | None] | None = None,
    ):
        super().__init__()
        self.result = result
        self._thumbnail_loader = thumbnail_loader
        self._build()

    def _build(self):
        self.setStyleSheet(
            """
            QWidget {
                background-color: #2a2a2a;
                border: 1px solid #3d3d3d;
                border-radius: 10px;
            }
            QWidget:hover { border-color: #0078d4; }
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 6px;
                color: white;
                padding: 6px 10px;
            }
            QPushButton:hover { background-color: #106ebe; }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.thumb = QLabel()
        self.thumb.setFixedSize(64, 64)
        self.thumb.setStyleSheet("background-color: #1f1f1f; border-radius: 6px;")
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.thumb)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        name = QLabel(self.result.mod.name or tr("nexus_unknown_mod_name"))
        name.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        author = QLabel(
            tr("nexus_by_author", author=self.result.mod.author or tr("not_installed"))
        )
        author.setStyleSheet("color: #cccccc; font-size: 11px;")
        info_col.addWidget(name)
        info_col.addWidget(author)
        layout.addLayout(info_col, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)

        details_btn = QPushButton(tr("nexus_view_details_button"))
        details_btn.clicked.connect(lambda: self.selected.emit(self.result))
        btn_col.addWidget(details_btn)

        dl_btn = QPushButton(tr("nexus_download_button"))
        dl_btn.clicked.connect(lambda: self.download_requested.emit(self.result))
        btn_col.addWidget(dl_btn)

        layout.addLayout(btn_col)

        self._load_thumbnail()

    def _load_thumbnail(self):
        url = self.result.mod.picture_url
        if not url or not self._thumbnail_loader:
            self.thumb.setText(tr("nexus_no_thumb"))
            self.thumb.setStyleSheet(
                "background-color: #1f1f1f; border-radius: 6px; color: #888888;"
            )
            return
        pix = self._thumbnail_loader(url)
        if pix is None or pix.isNull():
            self.thumb.setText(tr("nexus_no_thumb"))
            return
        self.thumb.setPixmap(
            pix.scaled(
                64,
                64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.result)
        super().mousePressEvent(event)


class NexusSearchPanel(QWidget):
    result_selected = Signal(object)  # NexusResult
    download_requested = Signal(object)  # NexusResult

    def __init__(
        self, *, thumbnail_loader: Callable[[str], QPixmap | None] | None = None
    ):
        super().__init__()
        self._thumbnail_loader = thumbnail_loader
        self._results: list[NexusResult] = []
        self._build()

    def _build(self):
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QLabel(tr("nexus_results_header"))
        header.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 600;")
        root.addWidget(header)

        self.status = QLabel(tr("nexus_results_empty"))
        self.status.setStyleSheet("color: #888888; font-size: 11px;")
        root.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")
        root.addWidget(self.scroll, 1)

        self.inner = QWidget()
        self.inner_layout = QVBoxLayout(self.inner)
        self.inner_layout.setContentsMargins(0, 0, 0, 0)
        self.inner_layout.setSpacing(8)
        self.inner_layout.addStretch()
        self.scroll.setWidget(self.inner)

    def set_status(self, text: str):
        self.status.setText(text)

    def clear_results(self):
        self._results = []
        # Clear cards
        while self.inner_layout.count():
            item = self.inner_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self.inner_layout.addStretch()
        self.status.setText(tr("nexus_results_empty"))

    def set_results(self, mods: list[NexusMod]):
        self.clear_results()
        self._results = [NexusResult(mod=m) for m in mods]
        if not self._results:
            return

        # Remove final stretch to append cards above it
        stretch_item = self.inner_layout.takeAt(self.inner_layout.count() - 1)
        if stretch_item and stretch_item.spacerItem() is None:
            # Unexpected; put it back
            self.inner_layout.addItem(stretch_item)

        for r in self._results:
            card = NexusResultCard(r, thumbnail_loader=self._thumbnail_loader)
            card.selected.connect(self.result_selected.emit)
            card.download_requested.connect(self.download_requested.emit)
            self.inner_layout.addWidget(card)

        self.inner_layout.addStretch()
        self.status.setText(tr("nexus_results_found", count=len(self._results)))
