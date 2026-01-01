"""
Right-side details panel for Nexus mods (modern card-style sidebar).
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from me3_manager.services.nexus_service import NexusMod, NexusModFile
from me3_manager.utils.translator import tr


def _fmt_int(val: int | None) -> str:
    if val is None:
        return "-"
    try:
        return f"{int(val):,}"
    except Exception:
        return str(val)


def _fmt_size_kb(size_kb: int | None) -> str:
    if size_kb is None:
        return "-"
    try:
        kb = float(int(size_kb))
        if kb < 1024:
            return f"{kb:.0f} KB"
        mb = kb / 1024.0
        if mb < 1024:
            return f"{mb:.2f} MB"
        gb = mb / 1024.0
        return f"{gb:.2f} GB"
    except Exception:
        return str(size_kb)
    return str(size_kb)


class NexusModDetailsSidebar(QWidget):
    close_clicked = Signal()
    open_page_clicked = Signal()
    check_update_clicked = Signal()
    install_clicked = Signal()
    link_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mod: NexusMod | None = None
        self._file: NexusModFile | None = None
        self._nexus_url: str | None = None
        self._target_width = 360
        self._min_height = 550  # Minimum height to ensure content is always visible
        self._animation: QPropertyAnimation | None = None
        self._build()
        # Set fixed width for the overlay
        self.setFixedWidth(self._target_width)
        # Raise to top so it appears above other widgets
        self.raise_()
        # Install event filter on parent to handle resizes
        if parent:
            parent.installEventFilter(self)

    def eventFilter(self, watched, event):
        """Handle parent resize events to reposition the sidebar."""
        from PySide6.QtCore import QEvent

        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            if self.isVisible():
                self._update_position()
        return super().eventFilter(watched, event)

    def _update_position(self):
        """Position the sidebar at the right edge of the parent.

        Uses the main window's geometry to calculate height, ensuring the sidebar
        is not affected by the mod list size.
        """
        if self.parent():
            parent_widget = self.parent()
            parent_rect = parent_widget.rect()

            # Get the main window to calculate available height
            main_window = parent_widget.window()
            if main_window:
                # Use main window height for a consistent sidebar size
                window_height = main_window.height()
                # Calculate height based on window, not parent widget
                height = max(self._min_height, window_height - 100)
            else:
                # Fallback to minimum height if no window
                height = max(self._min_height, parent_rect.height() - 48)

            # Position at right edge with some margin
            x = parent_rect.width() - self._target_width - 24
            y = 24  # Top margin
            self.setGeometry(x, y, self._target_width, height)

    def _adjust_content_margin(self, expand: bool):
        """Adjust the main content area to make room for sidebar."""
        try:
            parent = self.parent()
            if parent and hasattr(parent, "main_layout"):
                # Get current margins
                margins = parent.main_layout.contentsMargins()
                if expand:
                    # Add right margin to make room for sidebar
                    parent.main_layout.setContentsMargins(
                        margins.left(),
                        margins.top(),
                        self._target_width + 36,  # sidebar width + gap
                        margins.bottom(),
                    )
                    # Set minimum height on mods_widget to prevent clipping the sidebar
                    if hasattr(parent, "mods_widget"):
                        # Calculate minimum height based on sidebar needs
                        parent.mods_widget.setMinimumHeight(self._min_height - 80)
                else:
                    # Restore original right margin
                    parent.main_layout.setContentsMargins(
                        margins.left(),
                        margins.top(),
                        24,  # Original right margin
                        margins.bottom(),
                    )
                    # Remove minimum height constraint
                    if hasattr(parent, "mods_widget"):
                        parent.mods_widget.setMinimumHeight(0)
        except Exception:
            pass

    def show_animated(self):
        """Show the sidebar with a smooth fade-in animation."""
        if self.isVisible():
            return  # Already visible

        # Adjust content margin to make room for sidebar
        self._adjust_content_margin(expand=True)

        # Position the sidebar at the right edge of parent
        self._update_position()
        self.raise_()  # Ensure it's on top
        self.setVisible(True)

        self._start_opacity_animation(0.0, 1.0, 200, QEasingCurve.Type.OutCubic)

    def hide_animated(self):
        """Hide the sidebar with a smooth fade-out animation."""
        if not self.isVisible():
            return

        self._start_opacity_animation(
            1.0, 0.0, 150, QEasingCurve.Type.InCubic, self._on_hide_finished
        )

    def _start_opacity_animation(
        self, start: float, end: float, duration: int, easing, on_finished=None
    ):
        """Start an opacity animation with the given parameters."""
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)

        if self._animation:
            self._animation.stop()

        self._animation = QPropertyAnimation(effect, b"opacity")
        self._animation.setDuration(duration)
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        self._animation.setEasingCurve(easing)
        if on_finished:
            self._animation.finished.connect(on_finished)
        self._animation.start()

    def _on_hide_finished(self):
        """Called when hide animation finishes."""
        self.setVisible(False)
        self.setGraphicsEffect(None)  # Remove effect to restore normal rendering
        # Restore content margin
        self._adjust_content_margin(expand=False)

    def _build(self):
        self.setFixedWidth(self._target_width)
        self.setStyleSheet(
            """
            NexusModDetailsSidebar {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 12px;
            }
            QLabel {
                color: #ffffff;
                background: transparent;
            }
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 8px;
                color: white;
                padding: 10px 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton#Secondary {
                background-color: #3d3d3d;
                font-weight: 500;
                color: #ffffff;
            }
            QPushButton#Secondary:hover {
                background-color: #4d4d4d;
            }
            QPushButton#Secondary:pressed {
                background-color: #2d2d2d;
            }
            QPushButton#CloseBtn {
                background-color: transparent;
                border: none;
                color: #888888;
                padding: 0px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton#CloseBtn:hover {
                color: #ffffff;
            }
            #StatsContainer {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
            }
            #ScrollContent {
                background: transparent;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header row (outside scroll area so it's always visible)
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self.title = QLabel(tr("nexus_header"))
        self.title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header_row.addWidget(self.title)
        header_row.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        header_row.addWidget(self.close_btn)

        root.addLayout(header_row)

        # Scroll area for content - ensures content doesn't overlap when space is limited
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #4d4d4d;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5d5d5d;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Content widget inside scroll area
        content_widget = QWidget()
        content_widget.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(
            0, 0, 4, 0
        )  # Small right margin for scrollbar
        content_layout.setSpacing(12)

        # Thumbnail - scales with image
        self.thumb = QLabel()
        self.thumb.setMinimumHeight(80)
        self.thumb.setMaximumHeight(180)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet("""
            background-color: #2d2d2d;
            border-radius: 8px;
            color: #666666;
            font-size: 11px;
        """)
        self.thumb.setText(tr("nexus_no_thumb"))
        content_layout.addWidget(self.thumb)

        # Mod name - limit to 2 lines
        self.mod_name = QLabel("-")
        self.mod_name.setWordWrap(True)
        self.mod_name.setMaximumHeight(50)  # ~2 lines
        self.mod_name.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        content_layout.addWidget(self.mod_name)

        # Author - single line with elide
        self.author = QLabel("-")
        self.author.setStyleSheet("color: #888888; font-size: 11px;")
        self.author.setMaximumHeight(20)
        content_layout.addWidget(self.author)

        # Stats container
        stats_widget = QWidget()
        stats_widget.setObjectName("StatsContainer")
        stats_layout = QVBoxLayout(stats_widget)
        stats_layout.setContentsMargins(12, 10, 12, 10)
        stats_layout.setSpacing(6)

        self.endorsements = QLabel("-")
        self.total_dls = QLabel("-")
        self.version = QLabel("-")
        self.file_size = QLabel("-")
        self.cached = QLabel("-")

        def add_stat_row(label_key: str, value_label: QLabel):
            row = QHBoxLayout()
            row.setSpacing(8)
            k = QLabel(tr(label_key))
            k.setStyleSheet("color: #888888; font-size: 11px;")
            v = value_label
            v.setStyleSheet("color: #ffffff; font-size: 11px;")
            row.addWidget(k)
            row.addStretch()
            row.addWidget(v)
            stats_layout.addLayout(row)

        add_stat_row("nexus_endorsements_label", self.endorsements)
        add_stat_row("nexus_total_downloads_label", self.total_dls)
        add_stat_row("nexus_version_label", self.version)
        add_stat_row("nexus_file_size_label", self.file_size)
        add_stat_row("nexus_cached_label", self.cached)

        content_layout.addWidget(stats_widget)

        # Status
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #888888; font-size: 11px;")
        content_layout.addWidget(self.status)

        # Primary button
        self.open_page_btn = QPushButton(tr("nexus_open_page_button"))
        self.open_page_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_page_btn.clicked.connect(self.open_page_clicked.emit)
        content_layout.addWidget(self.open_page_btn)

        # Secondary buttons row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.check_update_btn = QPushButton(tr("nexus_check_update_button"))
        self.check_update_btn.setObjectName("Secondary")
        self.check_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_update_btn.clicked.connect(self.check_update_clicked.emit)
        actions_row.addWidget(self.check_update_btn, 1)

        self.install_btn = QPushButton(tr("nexus_install_button"))
        self.install_btn.setObjectName("Secondary")
        self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_btn.clicked.connect(self.install_clicked.emit)
        actions_row.addWidget(self.install_btn, 1)

        content_layout.addLayout(actions_row)

        # Mod root path input (for mods with unknown structure)
        self.folder_container = QWidget()
        folder_layout = QVBoxLayout(self.folder_container)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(4)

        folder_label = QLabel(tr("nexus_mod_folder_label"))
        folder_label.setStyleSheet("color: #888888; font-size: 10px;")
        folder_layout.addWidget(folder_label)

        from PySide6.QtWidgets import QLineEdit

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText(tr("nexus_mod_folder_placeholder"))
        self.folder_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 6px 8px;
                color: #ffffff;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        folder_layout.addWidget(self.folder_input)

        folder_hint = QLabel(tr("nexus_mod_folder_hint"))
        folder_hint.setWordWrap(True)
        folder_hint.setStyleSheet("color: #666666; font-size: 9px;")
        folder_layout.addWidget(folder_hint)

        content_layout.addWidget(self.folder_container)

        # Link button
        self.link_btn = QPushButton(tr("nexus_link_button"))
        self.link_btn.setObjectName("Secondary")
        self.link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link_btn.clicked.connect(self.link_clicked.emit)
        self.link_btn.setVisible(False)
        content_layout.addWidget(self.link_btn)

        content_layout.addStretch()

        # Set the content widget in the scroll area and add to root layout
        scroll_area.setWidget(content_widget)
        root.addWidget(scroll_area)

    def set_thumbnail(self, pix: QPixmap | None):
        if not pix or pix.isNull():
            self.thumb.setText(tr("nexus_no_thumb"))
            self.thumb.setFixedHeight(80)
            return
        # Scale image to fit width while keeping aspect ratio
        available_width = self._target_width - 32  # account for margins
        scaled = pix.scaledToWidth(
            available_width,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Limit height to reasonable max
        if scaled.height() > 180:
            scaled = pix.scaledToHeight(
                180,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.thumb.setFixedHeight(scaled.height())
        self.thumb.setPixmap(scaled)

    def set_details(self, mod: NexusMod | None, file: NexusModFile | None = None):
        self._mod = mod
        self._file = file
        if not mod:
            # Reset thumbnail too
            try:
                self.thumb.setPixmap(QPixmap())
            except Exception:
                pass
            self.thumb.setText(tr("nexus_no_thumb"))
            self.mod_name.setText("-")
            self.author.setText("-")
            self.endorsements.setText("-")
            self.total_dls.setText("-")
            self.version.setText("-")
            self.file_size.setText("-")
            self.cached.setText("-")
            self.status.setText("")
            self.open_page_btn.setEnabled(False)
            self.check_update_btn.setEnabled(False)
            self.install_btn.setEnabled(False)
            return

        self.mod_name.setText(mod.name or tr("nexus_unknown_mod_name"))
        self.author.setText(tr("nexus_by_author", author=mod.author or "-"))
        self.endorsements.setText(_fmt_int(mod.endorsement_count))
        self.total_dls.setText(_fmt_int(mod.total_downloads))
        # Show file version if available (actual installed version), otherwise mod page version
        self.version.setText(
            file.version if file and file.version else (mod.version or "-")
        )
        self.file_size.setText(_fmt_size_kb(file.size_kb if file else None))
        self.open_page_btn.setEnabled(True)
        self.check_update_btn.setEnabled(True)
        self.install_btn.setEnabled(True)

    def set_status(self, text: str):
        self.status.setText(text or "")

    def set_cached_text(self, text: str):
        self.cached.setText(text or "-")

    def set_nexus_url(self, url: str | None):
        self._nexus_url = url

    def current_url(self) -> str | None:
        return self._nexus_url

    def set_link_mode(self, *, linked: bool):
        # If not linked, show link button and disable update/install actions
        self.link_btn.setVisible(not linked)
        self.check_update_btn.setEnabled(linked and self._mod is not None)
        self.install_btn.setEnabled(linked and self._mod is not None)

    def current_mod(self) -> NexusMod | None:
        return self._mod

    def current_file(self) -> NexusModFile | None:
        return self._file

    def get_mod_root_path(self) -> str | None:
        """Get the user-specified folder path (empty string = auto-detect)."""
        text = self.folder_input.text().strip()
        return text if text else None

    def set_mod_root_path(self, path: str | None):
        """Set the folder path input value."""
        self.folder_input.setText(path or "")
