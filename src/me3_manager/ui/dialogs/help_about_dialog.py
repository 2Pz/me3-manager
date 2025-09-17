import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from me3_manager import __version__ as VERSION
from me3_manager.utils.platform_utils import PlatformUtils
from me3_manager.utils.status import Status
from me3_manager.utils.translator import tr


class HelpAboutDialog(QDialog):
    """A custom dialog for Help, About, and maintenance actions."""

    def __init__(self, main_window, initial_setup=False):
        super().__init__(main_window)
        self.main_window = main_window
        self.version_manager = self.main_window.version_manager
        self.setMinimumWidth(550)
        self.setStyleSheet("""
            QDialog { background-color: #252525; color: #ffffff; }
            QLabel { background-color: transparent; }
            QPushButton {
                background-color: #2d2d2d; border: 1px solid #3d3d3d;
                padding: 10px 16px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #3d3d3d; }
            QPushButton:disabled { background-color: #2a2a2a; color: #555555; border-color: #333333; }
            #TitleLabel { font-size: 18px; font-weight: bold; }
            #VersionLabel { color: #aaaaaa; }
            #HeaderLabel { font-size: 14px; font-weight: bold; margin-top: 15px; margin-bottom: 5px; }
            #DownloadStableButton { background-color: #0078d4; border: none; }
            #DownloadStableButton:hover { background-color: #005a9e; }
            #KoFiButton { background-color: #0078d4; border: none; font-weight: bold; }
            #KoFiButton:hover { background-color: #106ebe; }
            #VideoLinkLabel { color: #0078d4; text-decoration: underline; }
            #VideoLinkLabel:hover { color: #005a9e; }
            #WarningLabel { color: #ff4d4d; font-size: 16px; font-weight: bold; }
            #WarningInfoLabel { color: #f0c674; margin-bottom: 5px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel(tr("app_title"))
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        versions_text = f"{tr('manager_version', version=VERSION)}  |  {tr('me3_cli_version', version=self.main_window.me3_version)}"
        version_label = QLabel(versions_text)
        version_label.setObjectName("VersionLabel")
        layout.addWidget(version_label)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        self.close_button = QPushButton()

        if initial_setup:
            self.setWindowTitle(tr("me3_required_title"))

            warning_layout = QVBoxLayout()
            warning_layout.setSpacing(5)

            warning_label = QLabel(tr("me3_not_installed"))
            warning_label.setObjectName("WarningLabel")
            warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            warning_layout.addWidget(warning_label)

            warning_info_label = QLabel(tr("me3_not_installed_desc"))
            warning_info_label.setObjectName("WarningInfoLabel")
            warning_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            warning_info_label.setWordWrap(True)
            warning_layout.addWidget(warning_info_label)

            layout.addLayout(warning_layout)
            self.close_button.setText(tr("install_later"))
        else:
            self.setWindowTitle(tr("help_about_title"))
            description = QLabel(tr("help_about_label"))
            description.setWordWrap(True)
            layout.addWidget(description)
            self.close_button.setText(tr("close_button"))

        video_header = QLabel(tr("tutorial_label"))
        video_header.setObjectName("HeaderLabel")
        layout.addWidget(video_header)

        if sys.platform == "win32":
            video_link = QLabel(
                f'<a href="https://youtu.be/Xtshnmu6Y2o?si=bPdoqJ4RODliYSyX">{tr("win_tutorial_title")}</a>'
            )
        else:
            video_link = QLabel(
                f'<a href="https://www.youtube.com/watch?v=gMvBdP3TGDg">{tr("linux_tutorial_title")}</a>'
            )
        video_link.setObjectName("VideoLinkLabel")
        video_link.setOpenExternalLinks(True)
        video_link.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        layout.addWidget(video_link)

        actions_header = QLabel(tr("actions_label"))
        actions_header.setObjectName("HeaderLabel")
        layout.addWidget(actions_header)

        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(8)

        if sys.platform == "win32":
            self._setup_windows_buttons(actions_layout)
        else:
            self._setup_linux_buttons(actions_layout)

        layout.addLayout(actions_layout)
        layout.addStretch()

        button_box_layout = QHBoxLayout()
        support_button = QPushButton(tr("support_me"))
        support_button.setObjectName("KoFiButton")
        support_button.setCursor(Qt.CursorShape.PointingHandCursor)
        support_button.clicked.connect(self.open_kofi_link)
        button_box_layout.addWidget(support_button)

        button_box_layout.addStretch()

        self.close_button.clicked.connect(self.accept)
        button_box_layout.addWidget(self.close_button)

        layout.addLayout(button_box_layout)

    def open_kofi_link(self):
        PlatformUtils.open_url("https://ko-fi.com/2pz123")

    def _setup_windows_buttons(self, layout):
        self.update_cli_button = QPushButton(tr("update_me3_button"))
        self.update_cli_button.clicked.connect(self.handle_update_cli)
        if (
            self.main_window.config_manager.me3_info_manager.get_me3_installation_status()
            == Status.NOT_INSTALLED
        ):
            self.update_cli_button.setDisabled(True)
            self.update_cli_button.setToolTip(tr("me3_not_installed_tip"))
        layout.addWidget(self.update_cli_button)

        versions_info = self.version_manager.get_available_versions()

        btn_text = f"{tr('stable_installer_button_win')}"
        if versions_info["stable"]["version"]:
            btn_text += f" ({versions_info['stable']['version']})"
        self.stable_button = QPushButton(btn_text)
        self.stable_button.clicked.connect(self.handle_download)
        if not versions_info["stable"]["available"]:
            self.stable_button.setDisabled(True)
        layout.addWidget(self.stable_button)

        custom_btn_text = f"{tr('custom_installer_button_win')}"
        if versions_info["stable"]["version"]:
            custom_btn_text += f" ({versions_info['stable']['version']})"
        self.custom_button = QPushButton(custom_btn_text)
        self.custom_button.setObjectName("DownloadStableButton")
        self.custom_button.clicked.connect(self.handle_custom_install)
        if not versions_info["stable"]["available"]:
            self.custom_button.setDisabled(True)
        layout.addWidget(self.custom_button)

    def _setup_linux_buttons(self, layout):
        versions_info = self.version_manager.get_available_versions()
        btn_text = tr("stable_installer_button_linux")
        if versions_info["stable"]["version"]:
            btn_text += f" ({versions_info['stable']['version']})"
        self.stable_button = QPushButton(btn_text)
        self.stable_button.setObjectName("DownloadStableButton")
        self.stable_button.clicked.connect(self.handle_linux_install)
        if not versions_info["stable"]["available"]:
            self.stable_button.setDisabled(True)
        layout.addWidget(self.stable_button)

    def handle_custom_install(self):
        self.version_manager.custom_install_windows_me3()
        self.accept()

    def handle_update_cli(self):
        self.version_manager.update_me3_cli()
        self.accept()

    def handle_download(self):
        self.version_manager.download_windows_installer()
        self.accept()

    def handle_linux_install(self):
        self.version_manager.install_linux_me3()
        self.accept()
