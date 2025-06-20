from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QPushButton
)
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt

from core.config_manager import ConfigManager
from ui.game_page import GamePage
from ui.terminal import EmbeddedTerminal
from utils.resource_path import resource_path

class ModEngine3Manager(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.init_ui()
        self.setup_file_watcher()
    
    def init_ui(self):
        self.setWindowTitle("Mod Engine 3 Manager")
        self.setWindowIcon(QIcon(resource_path("resources/icon/icon.ico")))

        self.setGeometry(100, 100, 1200, 800)
        
        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QSplitter::handle {
                background-color: #3d3d3d;
            }
            QSplitter::handle:horizontal {
                width: 2px;
            }
        """)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create sidebar
        self.create_sidebar(splitter)
        
        # Create main content area
        self.create_content_area(splitter)
        
        # Set splitter sizes
        splitter.setSizes([250, 950])
        
        # Add splitter to main layout
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
    
    def create_sidebar(self, parent):
        """Create navigation sidebar"""
        sidebar = QWidget()
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: #252525;
                border-right: 1px solid #3d3d3d;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(8)
        
        # Title
        title = QLabel("Mod Engine 3")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 16px;")
        layout.addWidget(title)
        
        # Game buttons
        self.game_buttons = {}
        
        for game_name in ["Elden Ring", "Nightreign"]:
            btn = QPushButton(f"🎮 {game_name}")
            btn.setFixedHeight(45)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d;
                    border: 1px solid #3d3d3d;
                    border-radius: 8px;
                    padding: 8px 16px;
                    text-align: left;
                    font-size: 13px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #3d3d3d;
                    border-color: #4d4d4d;
                }
                QPushButton:checked {
                    background-color: #0078d4;
                    border-color: #0078d4;
                    color: white;
                }
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, name=game_name: self.switch_game(name))
            
            layout.addWidget(btn)
            self.game_buttons[game_name] = btn
        
        layout.addStretch()
        
        # Footer info
        footer = QLabel("v1.0.0\nMod Engine 3 Manager")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #888888; font-size: 10px; line-height: 1.4;")
        layout.addWidget(footer)
        
        parent.addWidget(sidebar)
    
    def create_content_area(self, parent):
        """Create main content area"""
        self.content_stack = QWidget()
        self.content_layout = QVBoxLayout(self.content_stack)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create game pages
        self.game_pages = {}
        for game_name in ["Elden Ring", "Nightreign"]:
            page = GamePage(game_name, self.config_manager)
            page.setVisible(False)
            self.content_layout.addWidget(page)
            self.game_pages[game_name] = page
        
        # Show first game by default
        self.switch_game("Elden Ring")

        self.terminal = EmbeddedTerminal()
        self.content_layout.addWidget(self.terminal)
        
        parent.addWidget(self.content_stack)
    
    def switch_game(self, game_name: str):
        """Switch to a different game page"""
        # Update button states
        for name, button in self.game_buttons.items():
            button.setChecked(name == game_name)
        
        # Show/hide pages
        for name, page in self.game_pages.items():
            page.setVisible(name == game_name)
    
    def setup_file_watcher(self):
        """Setup file system watcher"""
        self.config_manager.file_watcher.directoryChanged.connect(self.on_mods_changed)
    
    def on_mods_changed(self, path: str):
        """Handle changes in mod directories"""
        # Reload mods for all games
        for page in self.game_pages.values():
            page.load_mods()
