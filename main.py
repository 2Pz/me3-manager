import sys
import os 

from PyQt6.QtWidgets import QApplication

from ui.main_window import ModEngine3Manager

def main():
    if sys.platform == "linux":
        # Let Qt automatically detect and choose the best platform
        if 'QT_QPA_PLATFORM' in os.environ:
            del os.environ['QT_QPA_PLATFORM']
        
        # Enable Qt's automatic platform plugin selection with fallbacks
        # Qt will try platforms in order until one works
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = ''  # Use default paths
    
    app = QApplication(sys.argv)
    
    # Check what platform Qt actually chose at runtime
    if sys.platform == "linux":
        platform_name = app.platformName()
        print(f"Qt selected platform: {platform_name}")
        
        # If drag-drop issues persist, we can detect and handle them
        if platform_name == "wayland":
            print("Wayland detected - drag-drop compatibility may vary")
            # Could show a user notification about potential drag-drop issues
        
    # Set application properties
    app.setApplicationName("Mod Engine 3 Manager")
    app.setOrganizationName("ME3 Tools")
    
    # Apply dark theme
    app.setStyle("Fusion")
    
    # Create and show main window
    window = ModEngine3Manager()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
