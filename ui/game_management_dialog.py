from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, 
    QMessageBox, QInputDialog, QLabel, QLineEdit, QFormLayout, QListWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class GameManagementDialog(QDialog):
    """Dialog for managing games - add, remove, reorder"""
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Manage Games")
        self.setMinimumSize(600, 400)
        self.setStyleSheet("""
            
            QListWidget { 
                background-color: #2d2d2d; border: 1px solid #3d3d3d;
                border-radius: 4px; padding: 5px;
            }
            QListWidget::item { 
                padding: 8px; border-radius: 3px; margin: 1px;
            }
            QListWidget::item:selected { 
                background-color: #0078d4; 
            }
            QListWidget::item:hover { 
                background-color: #3d3d3d; 
            }
            QPushButton {
                background-color: #2d2d2d; border: 1px solid #3d3d3d;
                padding: 8px 16px; border-radius: 4px; font-weight: 500;
            }
            
        """)
        
        self.init_ui()
        self.populate_games_list()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Manage Games")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Games list
        self.games_list = QListWidget()
        self.games_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.games_list)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        self.add_button = QPushButton("Add Game")
        self.add_button.setObjectName("AddButton")
        self.add_button.clicked.connect(self.add_game)
        buttons_layout.addWidget(self.add_button)
        
        self.remove_button = QPushButton("Remove Game")
        self.remove_button.setObjectName("RemoveButton")
        self.remove_button.clicked.connect(self.remove_game)
        buttons_layout.addWidget(self.remove_button)
        
        self.restore_button = QPushButton("Restore Default")
        self.restore_button.setObjectName("RestoreButton")
        self.restore_button.clicked.connect(self.restore_default_game)
        buttons_layout.addWidget(self.restore_button)
        
        buttons_layout.addStretch()
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        buttons_layout.addWidget(close_button)
        
        layout.addLayout(buttons_layout)
        
        # Update button states
        self.games_list.itemSelectionChanged.connect(self.update_button_states)
        self.update_button_states()
    
    def populate_games_list(self):
        """Populate the games list with current games"""
        self.games_list.clear()
        
        for game_name in self.config_manager.get_game_order():
            item = QListWidgetItem(game_name)
            
            # Check if this is a default game
            default_games = self.config_manager._get_default_games()
            if game_name in default_games:
                item.setData(Qt.ItemDataRole.UserRole, "default")
                # Add indicator for default games
                item.setText(f"{game_name} (Default)")
            else:
                item.setData(Qt.ItemDataRole.UserRole, "custom")
            
            self.games_list.addItem(item)
    
    def update_button_states(self):
        """Update button enabled states based on selection"""
        selected_items = self.games_list.selectedItems()
        has_selection = len(selected_items) > 0
        
        self.remove_button.setEnabled(has_selection)
        
        # Only enable restore button for removed default games
        if has_selection:
            selected_game = selected_items[0].text().replace(" (Default)", "")
            is_default = selected_items[0].data(Qt.ItemDataRole.UserRole) == "default"
            self.restore_button.setEnabled(False)  # Default games are already present
        else:
            # Check if there are any default games missing
            default_games = self.config_manager._get_default_games()
            current_games = set(self.config_manager.games.keys())
            missing_defaults = set(default_games.keys()) - current_games
            self.restore_button.setEnabled(len(missing_defaults) > 0)
    
    def add_game(self):
        """Add a new custom game"""
        dialog = AddGameDialog(self.config_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.populate_games_list()
            self.parent().refresh_sidebar()
    
    def remove_game(self):
        """Remove the selected game"""
        selected_items = self.games_list.selectedItems()
        if not selected_items:
            return
        
        game_name = selected_items[0].text().replace(" (Default)", "")
        
        reply = QMessageBox.question(
            self, "Remove Game",
            f"Are you sure you want to remove '{game_name}'?\n\n"
            "This will delete all associated profiles, settings, and configurations.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.config_manager.remove_game(game_name)
                self.populate_games_list()
                self.parent().refresh_sidebar()
                QMessageBox.information(self, "Success", f"'{game_name}' has been removed successfully.")
            except Exception as e:
                QMessageBox.critical(self, tr("ERROR"), f"Failed to remove game: {str(e)}")
    
    def restore_default_game(self):
        """Restore missing default games"""
        default_games = self.config_manager._get_default_games()
        current_games = set(self.config_manager.games.keys())
        missing_defaults = set(default_games.keys()) - current_games
        
        if not missing_defaults:
            QMessageBox.information(self, "No Missing Games", "All default games are already present.")
            return
        
        # Show selection dialog if multiple missing
        if len(missing_defaults) == 1:
            game_to_restore = list(missing_defaults)[0]
        else:
            game_to_restore, ok = QInputDialog.getItem(
                self, "Restore Default Game",
                "Select a default game to restore:",
                sorted(missing_defaults), 0, False
            )
            if not ok:
                return
        
        try:
            game_config = default_games[game_to_restore]
            self.config_manager.add_game(
                name=game_to_restore,
                mods_dir=game_config["mods_dir"],
                profile=game_config["profile"],
                cli_id=game_config["cli_id"],
                executable=game_config["executable"]
            )
            
            self.populate_games_list()
            self.parent().refresh_sidebar()
            QMessageBox.information(self, "Success", f"'{game_to_restore}' has been restored successfully.")
        except Exception as e:
            QMessageBox.critical(self, tr("ERROR"), f"Failed to restore game: {str(e)}")


class AddGameDialog(QDialog):
    """Dialog for adding a new custom game"""
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Add New Game")
        self.setMinimumSize(500, 550)
        self.setStyleSheet("""\
            QLabel { color: #ffffff; }
            #DescriptionLabel { color: #bbbbbb; margin-bottom: 5px; }
            QLineEdit { 
                background-color: #2d2d2d; border: 1px solid #3d3d3d;
                padding: 8px; border-radius: 4px; color: #ffffff;
            }
            QLineEdit:focus { border-color: #0078d4; }
            QPushButton {
                background-color: #2d2d2d; border: 1px solid #3d3d3d;
                padding: 8px 16px; border-radius: 4px; font-weight: 500;
            }
            QPushButton:hover { background-color: #3d3d3d; }
            #AddButton { background-color: #0078d4; border: none; }
            #AddButton:hover { background-color: #005a9e; }
            #ExampleLabel { color: #888888; font-size: 11px; font-style: italic; }
        """)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Add New Game")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Description
        description = QLabel("Use this dialog to manually add a game supported by ME3.\n"
                             "This feature is intended for future updates where support for new games may be added.")
        description.setObjectName("DescriptionLabel")
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Form layout
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # Game Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Elden Ring")
        form_layout.addRow("Game Name:", self.name_input)
        
        name_example = QLabel("The display name for your game")
        name_example.setObjectName("ExampleLabel")
        form_layout.addRow("", name_example)
        
        # Mods Directory
        self.mods_dir_input = QLineEdit()
        self.mods_dir_input.setPlaceholderText("e.g., eldenring-mods")
        form_layout.addRow("Mods Directory:", self.mods_dir_input)
        
        mods_example = QLabel("Folder name where mods will be stored (no spaces, lowercase recommended)")
        mods_example.setObjectName("ExampleLabel")
        form_layout.addRow("", mods_example)
        
        # Profile File
        self.profile_input = QLineEdit()
        self.profile_input.setPlaceholderText("e.g., eldenring-default.me3")
        form_layout.addRow("Profile File:", self.profile_input)
        
        profile_example = QLabel("ME3 profile filename (should end with .me3)")
        profile_example.setObjectName("ExampleLabel")
        form_layout.addRow("", profile_example)
        
        # CLI ID
        self.cli_id_input = QLineEdit()
        self.cli_id_input.setPlaceholderText("e.g., elden-ring")
        form_layout.addRow("CLI ID:", self.cli_id_input)
        
        cli_example = QLabel("ME3 command-line identifier (lowercase, hyphens instead of spaces)")
        cli_example.setObjectName("ExampleLabel")
        form_layout.addRow("", cli_example)
        
        # Executable
        self.executable_input = QLineEdit()
        self.executable_input.setPlaceholderText("e.g., eldenring.exe")
        form_layout.addRow("Executable:", self.executable_input)
        
        exe_example = QLabel("Game executable filename")
        exe_example.setObjectName("ExampleLabel")
        form_layout.addRow("", exe_example)
        
        layout.addLayout(form_layout)
        
        # Auto-fill based on game name
        self.name_input.textChanged.connect(self.auto_fill_fields)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        add_button = QPushButton("Add Game")
        add_button.setObjectName("AddButton")
        add_button.clicked.connect(self.add_game)
        buttons_layout.addWidget(add_button)
        
        layout.addLayout(buttons_layout)
    
    def auto_fill_fields(self, text):
        """Auto-fill fields based on game name"""
        if not text.strip():
            return

        name_lower = text.lower().replace(" ", "").replace(":", "").replace("'", "")
        name_hyphenated = text.lower().replace(" ", "-").replace(":", "").replace("'", "")
        clean_name = text.replace(" ", "").replace(":", "").replace("'", "")

        self.mods_dir_input.setText(f"{name_lower}-mods")
        self.profile_input.setText(f"{name_lower}-default.me3")
        self.cli_id_input.setText(name_hyphenated)
        self.executable_input.setText(f"{clean_name}.exe")


    
    def add_game(self):
        """Validate and add the new game"""
        name = self.name_input.text().strip()
        mods_dir = self.mods_dir_input.text().strip()
        profile = self.profile_input.text().strip()
        cli_id = self.cli_id_input.text().strip()
        executable = self.executable_input.text().strip()
        
        # Validation
        if not all([name, mods_dir, profile, cli_id, executable]):
            QMessageBox.warning(self, "Validation Error", "All fields are required.")
            return
        
        if name in self.config_manager.games:
            QMessageBox.warning(self, "Validation Error", f"Game '{name}' already exists.")
            return
        
        if not profile.endswith('.me3'):
            QMessageBox.warning(self, "Validation Error", "Profile file must end with .me3")
            return
        
        # Check for conflicts with existing games
        existing_configs = self.config_manager.games.values()
        for config in existing_configs:
            if config["mods_dir"] == mods_dir:
                QMessageBox.warning(self, "Validation Error", f"Mods directory '{mods_dir}' is already used by another game.")
                return
            if config["profile"] == profile:
                QMessageBox.warning(self, "Validation Error", f"Profile file '{profile}' is already used by another game.")
                return
            if config["cli_id"] == cli_id:
                QMessageBox.warning(self, "Validation Error", f"CLI ID '{cli_id}' is already used by another game.")
                return
        
        try:
            self.config_manager.add_game(
                name=name,
                mods_dir=mods_dir,
                profile=profile,
                cli_id=cli_id,
                executable=executable
            )
            
            QMessageBox.information(self, "Success", f"Game '{name}' has been added successfully.")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, tr("ERROR"), f"Failed to add game: {str(e)}")