from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from me3_manager.utils.translator import tr


class DialogUtils:
    @staticmethod
    def ask_question(parent: QWidget, title: str, text: str) -> bool:
        reply = QMessageBox.question(
            parent,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return reply == QMessageBox.StandardButton.Yes


class NoEnterLineEdit(QLineEdit):
    """QLineEdit that doesn't activate buttons when Enter is pressed."""

    def keyPressEvent(self, event: QKeyEvent):
        """Override key press event to handle Enter/Return keys."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Consume the event - don't let it propagate to activate buttons
            event.accept()
            return
        # For all other keys, use default behavior
        super().keyPressEvent(event)


class StyleUtils:
    """Utility class for shared PySide6 stylesheets across dialogs."""

    @staticmethod
    def get_dialog_style() -> str:
        """Get dialog stylesheet"""
        return """
            QDialog {
                background-color: #2d2d2d;
                color: #ffffff;
            }
        """

    @staticmethod
    def get_group_style() -> str:
        """Get group box stylesheet"""
        return """
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #ffffff;
            }
        """

    @staticmethod
    def get_checkbox_style() -> str:
        """Get checkbox stylesheet"""
        return """
            QCheckBox {
                color: #ffffff;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #3d3d3d;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #106ebe;
                border-color: #106ebe;
            }
            QCheckBox::indicator:hover {
                border-color: #4d4d4d;
            }
        """

    @staticmethod
    def _get_input_widget_style(widget_type: str) -> str:
        """Get stylesheet for input widgets (QLineEdit, QComboBox, etc.)."""
        return f"""
            {widget_type} {{
                background-color: #3d3d3d;
                border: 2px solid #4d4d4d;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                color: #ffffff;
                min-height: 20px;
            }}
            {widget_type}:focus {{
                border-color: #0078d4;
            }}
            {widget_type}:hover {{
                border-color: #5d5d5d;
            }}
            {widget_type}:disabled {{
                background-color: #2d2d2d;
                color: #666666;
                border-color: #3d3d3d;
            }}
        """

    @staticmethod
    def _get_button_style(
        bg: str,
        hover: str,
        pressed: str,
        weight: str = "500",
        padding: str = "8px 16px",
        border: str = "none",
    ) -> str:
        """Get button stylesheet with specified colors."""
        return f"""
            QPushButton {{
                background-color: {bg};
                color: #ffffff;
                border: {border};
                border-radius: 6px;
                padding: {padding};
                font-size: 13px;
                font-weight: {weight};
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:pressed {{
                background-color: {pressed};
            }}
        """

    @staticmethod
    def get_lineedit_style() -> str:
        """Get line edit stylesheet"""
        return StyleUtils._get_input_widget_style("QLineEdit")

    @staticmethod
    def get_button_style() -> str:
        """Get regular button stylesheet"""
        return StyleUtils._get_button_style("#3d3d3d", "#4d4d4d", "#2d2d2d")

    @staticmethod
    def get_bordered_button_style() -> str:
        """Get bordered button stylesheet used in settings-style dialogs."""
        return StyleUtils._get_button_style(
            "#2d2d2d",
            "#3d3d3d",
            "#1d1d1d",
            padding="10px 20px",
            border="1px solid #3d3d3d",
        )

    @staticmethod
    def get_cancel_button_style() -> str:
        """Get cancel button stylesheet"""
        return StyleUtils._get_button_style(
            "#666666", "#777777", "#555555", padding="10px 20px"
        )

    @staticmethod
    def get_save_button_style() -> str:
        """Get save button stylesheet"""
        return StyleUtils._get_button_style(
            "#0078d4", "#106ebe", "#005a9e", weight="bold", padding="10px 20px"
        )

    @staticmethod
    def get_combobox_style() -> str:
        """Get combobox stylesheet"""
        return (
            StyleUtils._get_input_widget_style("QComboBox")
            + """
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                margin-right: 5px;
            }
            QComboBox::down-arrow:disabled {
                border-top-color: #666666;
            }
            QComboBox QAbstractItemView {
                background-color: #3d3d3d;
                border: 2px solid #4d4d4d;
                selection-background-color: #0078d4;
                color: #ffffff;
            }
        """
        )

    @staticmethod
    def get_dark_compact_widget_style(widget_type: str, font_size: str = "13px") -> str:
        """Get dark compact widget stylesheet for spinboxes, small combos, etc."""
        return f"""
            {widget_type} {{
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 4px 8px;
                color: #ffffff;
                font-size: {font_size};
            }}
        """

    @staticmethod
    def setup_standard_dialog_layout(
        dialog, title_text: str, title_font_size: int = 16
    ) -> QVBoxLayout:
        """Setup a standard vertical layout with a title label for dialogs."""
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel(title_text)
        title.setFont(QFont("Segoe UI", title_font_size, QFont.Weight.Bold))
        layout.addWidget(title)

        return layout

    @staticmethod
    def setup_standard_dialog_buttons(
        layout: QVBoxLayout, dialog, save_callback
    ) -> None:
        """Setup standard Cancel/Save buttons at the bottom of a dialog."""
        from PySide6.QtWidgets import QHBoxLayout, QPushButton

        from me3_manager.utils.translator import tr

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        dialog.cancel_btn = QPushButton(tr("cancel_button"))
        dialog.cancel_btn.setStyleSheet(StyleUtils.get_cancel_button_style())
        dialog.cancel_btn.clicked.connect(dialog.reject)

        dialog.save_btn = QPushButton(tr("save_button"))
        dialog.save_btn.setStyleSheet(StyleUtils.get_save_button_style())
        dialog.save_btn.clicked.connect(save_callback)

        button_layout.addWidget(dialog.cancel_btn)
        button_layout.addWidget(dialog.save_btn)

        layout.addLayout(button_layout)

    @staticmethod
    def setup_search_scroll_area(scroll) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QScrollArea

        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
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


class GameDialogBase(QDialog):
    """Base class for game-related dialogs with common initialization."""

    def __init__(
        self,
        game_name: str,
        config_manager,
        parent=None,
        title_key: str = "game_options_title",
        min_size: tuple[int, int] = (800, 560),
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.game_name = game_name
        self.config_manager = config_manager
        self.current_settings = {}

        self.setWindowTitle(tr(title_key, game_name=game_name))
        self.setModal(True)
        self.setMinimumSize(*min_size)
