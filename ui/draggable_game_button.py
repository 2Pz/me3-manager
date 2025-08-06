# ui/draggable_game_button.py

from PyQt6.QtWidgets import QPushButton, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint
from PyQt6.QtGui import QDrag, QPainter, QPixmap
from typing import List, Callable

class DraggableGameButton(QPushButton):
    """A draggable game button that supports drag and drop reordering"""
    
    # Signal emitted when button order changes
    order_changed = pyqtSignal(list)  # List of game names in new order
    
    def __init__(self, game_name: str, parent=None):
        super().__init__(game_name, parent)
        self.game_name = game_name
        self.drag_start_position = QPoint()
        self.drag_threshold = 10
        self.is_dragging = False
        self.setAcceptDrops(True)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
            self.is_dragging = False
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        
        # Check if we've moved far enough to start dragging
        distance = (event.position().toPoint() - self.drag_start_position).manhattanLength()
        if distance < self.drag_threshold:
            return
        
        # Mark as dragging to prevent click events
        self.is_dragging = True
        
        # Start drag operation
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.game_name)
        drag.setMimeData(mime_data)
        
        # Create drag pixmap
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setOpacity(0.7)
        self.render(painter)
        painter.end()
        drag.setPixmap(pixmap)
        
        # Execute drag
        drag.exec(Qt.DropAction.MoveAction)
        
        # Reset dragging state
        self.is_dragging = False
    
    def mouseReleaseEvent(self, event):
        # Only process click if we weren't dragging
        if not self.is_dragging:
            super().mouseReleaseEvent(event)
        else:
            # Reset dragging state
            self.is_dragging = False
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.source() != self:
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.source() != self:
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        if event.mimeData().hasText() and event.source() != self:
            dragged_game = event.mimeData().text()
            target_game = self.game_name
            
            # Get parent container to reorder buttons
            container = self.parent()
            if hasattr(container, 'reorder_games'):
                container.reorder_games(dragged_game, target_game)
            
            event.acceptProposedAction()
        else:
            event.ignore()


class DraggableGameContainer(QWidget):
    """Container widget that manages draggable game buttons"""
    
    # Signal emitted when game order changes
    game_order_changed = pyqtSignal(list)  # List of game names in new order
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.game_buttons = {}
        self.game_order = []
        
    def add_game_button(self, game_name: str, button_widget: DraggableGameButton):
        """Add a game button to the container"""
        self.game_buttons[game_name] = button_widget
        button_widget.setParent(self)
        self.layout.addWidget(button_widget)
        if game_name not in self.game_order:
            self.game_order.append(game_name)

    def remove_game_button(self, button):
        """Remove a game button from the container"""
        if button in self.game_buttons.values():
            button.setParent(None)
            # Remove from internal tracking
            for game_name, btn in list(self.game_buttons.items()):
                if btn == button:
                    del self.game_buttons[game_name]
                    break

            # Update layout
            self._reorder_widgets()

    
    def set_game_order(self, new_order: List[str]):
        """Set the order of game buttons"""
        self.game_order = new_order.copy()
        self._reorder_widgets()
    
    def _reorder_widgets(self):
        """Reorder widgets in the layout based on game_order"""
        # Remove all widgets from layout without changing parent
        widgets_to_reorder = []
        for i in reversed(range(self.layout.count())):
            item = self.layout.takeAt(i)
            if item.widget():
                widgets_to_reorder.append(item.widget())
        
        # Add widgets back in the correct order
        for game_name in self.game_order:
            if game_name in self.game_buttons:
                widget = self.game_buttons[game_name]
                self.layout.addWidget(widget)
    
    def reorder_games(self, dragged_game: str, target_game: str):
        """Reorder games based on drag and drop"""
        if dragged_game == target_game:
            return
        
        # Get current positions
        dragged_index = self.game_order.index(dragged_game) if dragged_game in self.game_order else -1
        target_index = self.game_order.index(target_game) if target_game in self.game_order else -1
        
        if dragged_index == -1 or target_index == -1:
            return
        
        # Create a new order list
        new_order = self.game_order.copy()
        
        # Remove the dragged item
        new_order.remove(dragged_game)
        
        # Find the new target index (after removal)
        new_target_index = new_order.index(target_game)
        
        # If dragging from top to bottom, insert after the target
        # If dragging from bottom to top, insert before the target
        if dragged_index < target_index:
            # Dragging downward - insert after target
            new_order.insert(new_target_index + 1, dragged_game)
        else:
            # Dragging upward - insert before target
            new_order.insert(new_target_index, dragged_game)
        
        # Update the order
        self.game_order = new_order
        
        # Reorder widgets and emit signal
        self._reorder_widgets()
        self.game_order_changed.emit(self.game_order.copy())
    
    def get_game_order(self) -> List[str]:
        """Get current game order"""
        return self.game_order.copy()
