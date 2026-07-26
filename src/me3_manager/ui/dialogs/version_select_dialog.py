import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressDialog,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from me3_manager.services.me3_service import Me3Service
from me3_manager.utils.translator import tr

log = logging.getLogger(__name__)


class FetchReleasesThread(QThread):
    """Background thread to fetch all ME3 releases from GitHub."""

    releases_fetched = Signal(list)

    def __init__(self, me3_service: Me3Service):
        super().__init__()
        self.me3_service = me3_service

    def run(self):
        releases = self.me3_service.fetch_all_releases(per_page=30)
        self.releases_fetched.emit(releases)


class VersionSelectDialog(QDialog):
    """Dialog that lets the user pick a specific ME3 version to install."""

    def __init__(self, parent, releases: list[dict], current_version: str | None):
        super().__init__(parent)
        self.releases = releases
        self.current_version = current_version
        self.selected_tag: str | None = None
        self._init_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _init_ui(self):
        self.setWindowTitle(tr("select_version_title"))
        self.setMinimumWidth(560)
        self.setMinimumHeight(460)

        from me3_manager.ui.dialogs.dialog_utils import StyleUtils

        self.setStyleSheet(f"""
            QDialog {{ background-color: #252525; color: #ffffff; }}
            QLabel {{ background-color: transparent; color: #ffffff; }}
            {StyleUtils.get_bordered_button_style()}
            QPushButton:disabled {{
                background-color: #2a2a2a; color: #555555; border-color: #333333;
            }}
            #InstallButton {{
                background-color: #0078d4; border: none;
            }}
            #InstallButton:hover {{ background-color: #005a9e; }}
            #InstallButton:disabled {{
                background-color: #2a2a2a; color: #555555;
            }}
            QComboBox {{
                background-color: #2d2d2d; border: 1px solid #3d3d3d;
                border-radius: 6px; padding: 8px 12px; color: #ffffff;
                font-size: 14px; min-height: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #252525; color: #ffffff;
                selection-background-color: #0078d4;
                border: 1px solid #3d3d3d;
            }}
            QComboBox:focus {{ border-color: #0078d4; }}
            QTextBrowser {{
                background-color: #1e1e1e; border: 1px solid #3d3d3d;
                border-radius: 6px; padding: 10px; color: #cccccc;
                font-size: 13px;
            }}
            #SectionHeader {{
                font-size: 15px; font-weight: bold; color: #ffffff;
            }}
            #CurrentVersionLabel {{
                color: #90EE90; font-size: 13px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Title
        title = QLabel(tr("select_version_title"))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Description
        desc = QLabel(tr("select_version_description"))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Current version indicator
        if self.current_version:
            current_label = QLabel(
                tr("installed_version_label", version=self.current_version)
            )
            current_label.setObjectName("CurrentVersionLabel")
            layout.addWidget(current_label)

        # Version selector
        version_header = QLabel(tr("select_version_title"))
        version_header.setObjectName("SectionHeader")
        layout.addWidget(version_header)

        self.version_combo = QComboBox()
        self._populate_versions()
        self.version_combo.currentIndexChanged.connect(self._on_version_changed)
        layout.addWidget(self.version_combo)

        # Release notes
        notes_header = QLabel(tr("release_notes_label"))
        notes_header.setObjectName("SectionHeader")
        layout.addWidget(notes_header)

        self.notes_browser = QTextBrowser()
        self.notes_browser.setOpenExternalLinks(True)
        self.notes_browser.setMinimumHeight(160)
        layout.addWidget(self.notes_browser, 1)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton(tr("cancel_button"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.install_btn = QPushButton(tr("install_version_button"))
        self.install_btn.setObjectName("InstallButton")
        self.install_btn.clicked.connect(self._on_install_clicked)
        button_layout.addWidget(self.install_btn)

        layout.addLayout(button_layout)

        # Trigger initial selection
        if self.version_combo.count() > 0:
            self._on_version_changed(0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_versions(self):
        """Fill the combo box with version tags from the releases list."""
        latest_tag = self.releases[0].get("tag_name") if self.releases else None

        for release in self.releases:
            tag = release.get("tag_name", "")
            display = tag

            suffixes = []
            if tag == latest_tag:
                suffixes.append(tr("latest_label"))
            if self.current_version and tag == self.current_version:
                suffixes.append(tr("current_label"))
            if suffixes:
                display = f"{tag}  {' '.join(suffixes)}"

            self.version_combo.addItem(display, tag)

    def _on_version_changed(self, index: int):
        """Update the release notes panel when a version is selected."""
        if index < 0 or index >= len(self.releases):
            return

        tag = self.version_combo.itemData(index)
        release = next((r for r in self.releases if r.get("tag_name") == tag), None)
        if release:
            self.notes_browser.setMarkdown(release.get("body", ""))
        else:
            self.notes_browser.clear()

        # Disable install if user picked the already-installed version
        is_same = self.current_version and tag == self.current_version
        self.install_btn.setEnabled(not is_same)

    def _on_install_clicked(self):
        """Store the selected tag and accept the dialog."""
        index = self.version_combo.currentIndex()
        if index >= 0:
            self.selected_tag = self.version_combo.itemData(index)
        self.accept()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_selected_version(self) -> str | None:
        """Return the version tag the user chose, or None if cancelled."""
        return self.selected_tag


def show_version_select_dialog(
    parent_widget,
    version_manager,
    on_version_selected,
):
    """Fetch releases in background, then show the version select dialog.

    Args:
        parent_widget: Parent QWidget for the progress dialog.
        version_manager: The ME3VersionManager instance.
        on_version_selected: Callback ``f(version_tag: str)`` invoked when a
            version is chosen and confirmed.
    """
    progress = QProgressDialog(
        tr("fetching_versions"),
        None,  # no cancel button
        0,
        0,
        parent_widget,
    )
    progress.setWindowTitle(tr("select_version_title"))
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setCancelButton(None)
    progress.setMinimumWidth(300)
    progress.show()

    thread = FetchReleasesThread(version_manager.me3_service)

    def _on_fetched(releases: list[dict]):
        progress.close()
        thread.quit()
        thread.wait()

        if not releases:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                parent_widget,
                tr("ERROR"),
                tr("no_versions_found"),
            )
            return

        # Determine current installed version tag
        current = version_manager.config_manager.get_me3_version()
        current_tag = None
        if current:
            current_tag = current if current.startswith("v") else f"v{current}"

        dialog = VersionSelectDialog(parent_widget, releases, current_tag)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chosen = dialog.get_selected_version()
            if chosen:
                on_version_selected(chosen)

    thread.releases_fetched.connect(_on_fetched)
    thread.start()

    # Keep references alive until the thread finishes
    parent_widget._version_fetch_thread = thread
    parent_widget._version_progress = progress
