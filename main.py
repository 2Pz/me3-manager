# main.py

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from ui.main_window import ModEngine3Manager
from utils.resource_path import resource_path

def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Mod Engine 3 Manager")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("ME3 Tools")
    
    # Apply dark theme
    app.setStyle("Fusion")
    
    # Create and show main window
    window = ModEngine3Manager()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()