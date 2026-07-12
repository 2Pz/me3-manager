from PySide6.QtWidgets import QVBoxLayout, QWidget


class BaseSearchPanel(QWidget):
    """Base panel for search results."""

    def __init__(self):
        super().__init__()
        self.root_layout = QVBoxLayout(self)
        self.status = None  # Subclasses must set this in their UI setup

    def _setup_base_ui(self, spacing: int = 8):
        self.setStyleSheet("background: transparent;")
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(spacing)

    def set_status(self, text: str):
        """Update the status label text."""
        if self.status is not None:
            self.status.setText(text)

    def _clear_layout(self, layout):
        """Helper to clear all items in a layout."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())
