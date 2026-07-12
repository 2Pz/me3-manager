from PySide6.QtWidgets import QDialog, QHBoxLayout, QScrollArea, QVBoxLayout

from me3_manager.ui.dialogs.dialog_utils import NoEnterLineEdit, StyleUtils


def test_get_dialog_style(qtbot):
    style = StyleUtils.get_dialog_style()
    assert "background-color:" in style


def test_setup_standard_dialog_layout(qtbot):
    dialog = QDialog()
    qtbot.addWidget(dialog)
    layout = StyleUtils.setup_standard_dialog_layout(dialog, "Test Title", 14)
    assert isinstance(layout, QVBoxLayout)
    assert layout.count() == 1

    # Check title widget
    title_widget = layout.itemAt(0).widget()
    assert title_widget.text() == "Test Title"


def test_setup_standard_dialog_buttons(qtbot):
    dialog = QDialog()
    qtbot.addWidget(dialog)
    layout = QVBoxLayout(dialog)

    # Mock callback
    saved = False

    def mock_save():
        nonlocal saved
        saved = True

    StyleUtils.setup_standard_dialog_buttons(layout, dialog, mock_save)

    # Button layout should be added
    assert layout.count() == 1
    btn_layout = layout.itemAt(0).layout()
    assert isinstance(btn_layout, QHBoxLayout)

    # Check cancel and save buttons
    assert hasattr(dialog, "cancel_btn")
    assert hasattr(dialog, "save_btn")

    dialog.save_btn.click()
    assert saved is True


def test_setup_search_scroll_area(qtbot):
    scroll = QScrollArea()
    qtbot.addWidget(scroll)
    StyleUtils.setup_search_scroll_area(scroll)

    assert scroll.widgetResizable() is True
    assert "background: transparent" in scroll.styleSheet()


def test_no_enter_line_edit(qtbot):
    widget = NoEnterLineEdit()
    qtbot.addWidget(widget)
    widget.setText("test")
    assert widget.text() == "test"
