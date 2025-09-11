from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from me3_manager.utils.translator import tr


class DependencyWidget(QWidget):
    """Widget for managing a single dependency (load_before/load_after)"""

    removed = pyqtSignal()

    def __init__(
        self,
        dependency_data: dict[str, Any] = None,
        available_mods: list[str] = None,
        parent_list_widget=None,
    ):
        super().__init__()
        self.available_mods = available_mods or []
        self.parent_list_widget = parent_list_widget
        self.current_selection = ""

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Mod ID combo box
        self.mod_combo = QComboBox()
        self.mod_combo.setEditable(True)

        if dependency_data and "id" in dependency_data:
            self.current_selection = dependency_data["id"]

        self.mod_combo.currentTextChanged.connect(self.on_selection_changed)
        layout.addWidget(self.mod_combo)

        # Optional checkbox
        self.optional_check = QCheckBox(tr("optional"))
        if dependency_data:
            self.optional_check.setChecked(dependency_data.get("optional", False))
        layout.addWidget(self.optional_check)

        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(25, 25)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #cc4444; color: white; border: none;
                border-radius: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #dd5555; }
        """)
        remove_btn.clicked.connect(self.removed.emit)
        layout.addWidget(remove_btn)

        self.setLayout(layout)
        self.update_available_mods()

    def on_selection_changed(self, new_text: str):
        self.current_selection = new_text.strip()
        if self.parent_list_widget:
            self.parent_list_widget.update_all_widgets()

    def update_available_mods(self):
        if not self.parent_list_widget:
            return
        available_mods = self.parent_list_widget.get_available_mods_for_widget(self)
        if self.current_selection and self.current_selection not in available_mods:
            available_mods.append(self.current_selection)
        available_mods.sort()
        current_text = self.mod_combo.currentText()
        self.mod_combo.blockSignals(True)
        self.mod_combo.clear()
        self.mod_combo.addItems(available_mods)
        if current_text in available_mods:
            self.mod_combo.setCurrentText(current_text)
        elif self.current_selection in available_mods:
            self.mod_combo.setCurrentText(self.current_selection)
        self.mod_combo.blockSignals(False)

    def get_dependency_data(self) -> dict[str, Any]:
        return {
            "id": self.mod_combo.currentText().strip(),
            "optional": self.optional_check.isChecked(),
        }


class DependencyListWidget(QWidget):
    """Widget for managing a list of dependencies"""

    def __init__(
        self,
        title: str,
        dependencies: list[dict[str, Any]] = None,
        available_mods: list[str] = None,
    ):
        super().__init__()
        self.available_mods = available_mods or []
        self.dependency_widgets = []
        self.other_list_widget = None

        layout = QVBoxLayout()
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(title))
        header_layout.addStretch()
        add_btn = QPushButton(tr("add_dependency"))
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4; color: white; border: none;
                border-radius: 4px; padding: 4px 8px;
            }
            QPushButton:hover { background-color: #106ebe; }
        """)
        add_btn.clicked.connect(self.add_dependency)
        header_layout.addWidget(add_btn)
        layout.addLayout(header_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(150)
        self.dependencies_widget = QWidget()
        self.dependencies_layout = QVBoxLayout(self.dependencies_widget)
        self.dependencies_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.dependencies_widget)
        layout.addWidget(scroll)
        self.setLayout(layout)

        if dependencies:
            for dep in dependencies:
                self.add_dependency(dep)

    def set_other_list_widget(self, other_widget):
        self.other_list_widget = other_widget

    def get_used_mod_ids(self) -> set:
        return {
            w.mod_combo.currentText().strip()
            for w in self.dependency_widgets
            if w.mod_combo.currentText().strip()
        }

    def get_available_mods_for_widget(self, current_widget) -> list[str]:
        used_in_this_list = {
            w.mod_combo.currentText().strip()
            for w in self.dependency_widgets
            if w != current_widget and w.mod_combo.currentText().strip()
        }
        used_in_other_list = (
            self.other_list_widget.get_used_mod_ids()
            if self.other_list_widget
            else set()
        )
        all_used = used_in_this_list | used_in_other_list
        return [mod for mod in self.available_mods if mod not in all_used]

    def add_dependency(self, dependency_data: dict[str, Any] = None):
        dep_widget = DependencyWidget(dependency_data, self.available_mods, self)
        dep_widget.removed.connect(lambda: self.remove_dependency(dep_widget))
        self.dependency_widgets.append(dep_widget)
        self.dependencies_layout.addWidget(dep_widget)
        self.update_all_widgets()

    def remove_dependency(self, widget: DependencyWidget):
        if widget in self.dependency_widgets:
            self.dependency_widgets.remove(widget)
            self.dependencies_layout.removeWidget(widget)
            widget.deleteLater()
            self.update_all_widgets()

    def update_all_widgets(self):
        for widget in self.dependency_widgets:
            widget.update_available_mods()
        if self.other_list_widget:
            for widget in self.other_list_widget.dependency_widgets:
                widget.update_available_mods()

    def get_dependencies(self) -> list[dict[str, Any]]:
        return [
            w.get_dependency_data()
            for w in self.dependency_widgets
            if w.get_dependency_data()["id"]
        ]


class AdvancedModOptionsDialog(QDialog):
    """Dialog for configuring advanced mod options"""

    def __init__(
        self,
        mod_path: str,
        mod_name: str,
        is_folder_mod: bool,
        current_options: dict[str, Any],
        available_mods: list[str],
        parent=None,
    ):
        super().__init__(parent)
        self.mod_path = mod_path
        self.mod_name = mod_name
        self.is_folder_mod = is_folder_mod
        self.current_options = current_options or {}

        processed_available_mods = []
        for mod in available_mods:
            if mod != mod_name:
                if (
                    not self.is_folder_mod
                    and not mod.endswith(".dll")
                    and "/" not in mod
                    and "\\" not in mod
                ):
                    processed_available_mods.append(f"{mod}.dll")
                else:
                    processed_available_mods.append(mod)
        self.available_mods = processed_available_mods

        self.setWindowTitle(tr("advanced_options", mod_name=mod_name))
        self.setMinimumSize(600, 500)
        self.resize(700, 680)

        self.setup_ui()
        self.load_current_options()

    def _convert_dependencies_to_dict_format(self, dependencies):
        """Convert dependencies from string or dict format to a consistent dictionary format for the UI."""
        if not dependencies:
            return []
        converted = []
        for dep in dependencies:
            if isinstance(dep, str):
                converted.append({"id": dep, "optional": False})
            elif isinstance(dep, dict):
                if "optional" not in dep:
                    dep["optional"] = False
                converted.append(dep)
        return converted

    def _format_dependencies_for_saving(
        self, dependencies: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Formats dependencies for saving.
        Based on observed parser behavior, BOTH packages and natives require the Dependent object format.
        """
        formatted_deps = []
        for dep in dependencies:
            dep_id = dep.get("id", "").strip()
            if dep_id:
                is_optional = dep.get("optional", False)
                formatted_deps.append({"id": dep_id, "optional": is_optional})
        return formatted_deps

    def get_options(self) -> dict[str, Any]:
        """Get the configured options (excluding enabled field)"""
        options = {}

        # Load order - always format as Dependent objects
        options["load_before"] = self._format_dependencies_for_saving(
            self.load_before_widget.get_dependencies()
        )
        options["load_after"] = self._format_dependencies_for_saving(
            self.load_after_widget.get_dependencies()
        )

        # Advanced options (DLL only)
        if not self.is_folder_mod:
            if hasattr(self, "optional_check"):
                options["optional"] = self.optional_check.isChecked()

            if hasattr(self, "init_type_combo"):
                init_type = self.init_type_combo.currentText()
                if init_type == "Function Call":
                    function_name = self.init_function_edit.text().strip()
                    options["initializer"] = (
                        {"function": function_name} if function_name else None
                    )
                elif init_type == "Delay":
                    delay_ms = self.init_delay_spin.value()
                    options["initializer"] = (
                        {"delay": {"ms": delay_ms}} if delay_ms > 0 else None
                    )
                else:
                    options["initializer"] = None

                finalizer = self.finalizer_edit.text().strip()
                options["finalizer"] = finalizer if finalizer else None

        return options

    def setup_ui(self):
        layout = QVBoxLayout()
        header = QLabel(tr("advanced_options", mod_name=self.mod_name))
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #ffffff; margin-bottom: 15px;")
        layout.addWidget(header)

        mod_type = "DLL Mod" if not self.is_folder_mod else "Package Mod"
        type_label = QLabel(tr("mod_type", mod_type=mod_type))
        type_label.setStyleSheet(
            "color: #888888; font-size: 11px; margin-bottom: 10px;"
        )
        layout.addWidget(type_label)

        self.tabs = QTabWidget()
        self.setup_load_order_tab()
        if not self.is_folder_mod:
            self.setup_advanced_tab()
        layout.addWidget(self.tabs)

        clear_layout = QHBoxLayout()
        clear_layout.addStretch()
        clear_btn = QPushButton(tr("clear_all"))
        clear_btn.setStyleSheet("""
            QPushButton { background-color: #cc4444; color: white; border: none; border-radius: 6px; padding: 8px 16px; font-size: 12px; }
            QPushButton:hover { background-color: #dd5555; }
        """)
        clear_btn.clicked.connect(self.clear_all_options)
        clear_layout.addWidget(clear_btn)
        layout.addLayout(clear_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self.setLayout(layout)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #ffffff; }
            QTabWidget::pane { border: 1px solid #404040; background-color: #242424; border-radius: 6px; }
            QTabWidget::tab-bar { alignment: left; }
            QTabBar::tab { background-color: #333333; color: #cccccc; padding: 12px 24px; margin-right: 2px; font-size: 13px; border-top-left-radius: 6px; border-top-right-radius: 6px; min-width: 60px; }
            QTabBar::tab:selected { background-color: #0078d4; color: #ffffff; }
            QTabBar::tab:hover:!selected { background-color: #404040; color: #ffffff; }
            QGroupBox { font-weight: bold; border: 2px solid #404040; border-radius: 8px; margin-top: 12px; padding-top: 12px; color: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px 0 8px; color: #0078d4; }
            QCheckBox, QLabel { color: #e0e0e0; }
            QLineEdit, QSpinBox, QComboBox, QTextEdit { background-color: #1a1a1a; border: 1px solid #404040; border-radius: 5px; padding: 6px 8px; color: #ffffff; }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus { border-color: #0078d4; background-color: #202020; }
            QLineEdit:hover, QSpinBox:hover, QComboBox:hover, QTextEdit:hover { border-color: #555555; }
        """)

    def setup_load_order_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        desc = QLabel(tr("load_order_description"))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #cccccc; margin-bottom: 10px;")
        layout.addWidget(desc)
        load_before_data = self._convert_dependencies_to_dict_format(
            self.current_options.get("load_before", [])
        )
        load_after_data = self._convert_dependencies_to_dict_format(
            self.current_options.get("load_after", [])
        )
        self.load_before_widget = DependencyListWidget(
            tr("load_before"), load_before_data, self.available_mods
        )
        layout.addWidget(self.load_before_widget)
        self.load_after_widget = DependencyListWidget(
            tr("load_after"), load_after_data, self.available_mods
        )
        layout.addWidget(self.load_after_widget)
        self.load_before_widget.set_other_list_widget(self.load_after_widget)
        self.load_after_widget.set_other_list_widget(self.load_before_widget)
        help_text = QLabel(f"""
            <b>{tr("load_order_help_title")}:</b><br>
            • <b>{tr("load_before")}:</b> {tr("load_order_help_load_before")}<br>
            • <b>{tr("load_after")}:</b> {tr("load_order_help_load_after")}<br>
            • <b>{tr("optional")}:</b> {tr("load_order_help_optional")}<br>
            • <b>{tr("note")}:</b> {tr("load_order_help_note")}<br>
            • {tr("load_order_help_runtime")}""")
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #888888; font-size: 11px; margin-top: 10px;")
        layout.addWidget(help_text)
        tab.setLayout(layout)
        self.tabs.addTab(tab, tr("load_order"))

    def setup_advanced_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        optional_group = QGroupBox(tr("optional_setting"))
        optional_layout = QFormLayout()
        self.optional_check = QCheckBox(tr("optional"))
        self.optional_check.setToolTip(tr("optional_setting_tooltip"))
        optional_layout.addRow("Optional:", self.optional_check)
        optional_group.setLayout(optional_layout)
        layout.addWidget(optional_group)
        init_group = QGroupBox(tr("initializer"))
        init_layout = QVBoxLayout()
        self.init_type_combo = QComboBox()
        self.init_type_combo.addItems(["None", "Function Call", "Delay"])
        self.init_type_combo.currentTextChanged.connect(self.on_init_type_changed)
        init_layout.addWidget(QLabel(tr("initializer_type")))
        init_layout.addWidget(self.init_type_combo)
        self.init_function_edit = QLineEdit()
        self.init_function_edit.setPlaceholderText(tr("function_name_placeholder"))
        self.init_function_label = QLabel(tr("function_name_label"))
        init_layout.addWidget(self.init_function_label)
        init_layout.addWidget(self.init_function_edit)
        self.init_delay_spin = QSpinBox()
        self.init_delay_spin.setRange(0, 60000)
        self.init_delay_spin.setSuffix(" ms")
        self.init_delay_spin.setValue(1000)
        self.init_delay_label = QLabel(tr("delay_ms_label"))
        init_layout.addWidget(self.init_delay_label)
        init_layout.addWidget(self.init_delay_spin)
        init_group.setLayout(init_layout)
        layout.addWidget(init_group)
        final_group = QGroupBox(tr("finalizer"))
        final_layout = QFormLayout()
        self.finalizer_edit = QLineEdit()
        self.finalizer_edit.setPlaceholderText(tr("finalizer_placeholder"))
        self.finalizer_edit.setToolTip(tr("finalizer_tooltip"))
        final_layout.addRow(tr("cleanup_function"), self.finalizer_edit)
        final_group.setLayout(final_layout)
        layout.addWidget(final_group)
        help_text = QLabel(f"""
            <b>{tr("native_module_help_title")}:</b><br>
            • <b>{tr("native_module_help_optional_title")}</b> {tr("native_module_help_optional_description")}<br>
            • <b>{tr("native_module_help_initializer_title")}</b> {tr("native_module_help_initializer_description")}<br>
            - <b>{tr("native_module_help_function_title")}</b> {tr("native_module_help_function_description")}<br>
            - <b>{tr("native_module_help_delay_title")}</b> {tr("native_module_help_delay_description")}<br>
            • <b>{tr("native_module_help_finalizer_title")}</b> {tr("native_module_help_finalizer_description")}""")
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #888888; font-size: 11px; margin-top: 10px;")
        layout.addWidget(help_text)
        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, tr("advanced"))
        self.on_init_type_changed("None")

    def on_init_type_changed(self, init_type: str):
        if not hasattr(self, "init_function_edit"):
            return
        show_function = init_type == "Function Call"
        show_delay = init_type == "Delay"
        self.init_function_label.setVisible(show_function)
        self.init_function_edit.setVisible(show_function)
        self.init_delay_label.setVisible(show_delay)
        self.init_delay_spin.setVisible(show_delay)

    def load_current_options(self):
        if not self.is_folder_mod and hasattr(self, "optional_check"):
            self.optional_check.setChecked(self.current_options.get("optional", False))
        if not self.is_folder_mod and hasattr(self, "init_type_combo"):
            initializer = self.current_options.get("initializer")
            if initializer is None:
                self.init_type_combo.setCurrentText("None")
            elif isinstance(initializer, dict):
                if "function" in initializer:
                    self.init_type_combo.setCurrentText("Function Call")
                    self.init_function_edit.setText(initializer["function"])
                elif "delay" in initializer:
                    self.init_type_combo.setCurrentText("Delay")
                    self.init_delay_spin.setValue(initializer["delay"].get("ms", 1000))
            finalizer = self.current_options.get("finalizer")
            if finalizer:
                self.finalizer_edit.setText(finalizer)

    def clear_all_options(self):
        if not self.is_folder_mod and hasattr(self, "optional_check"):
            self.optional_check.setChecked(False)
        for widget in self.load_before_widget.dependency_widgets[:]:
            self.load_before_widget.remove_dependency(widget)
        for widget in self.load_after_widget.dependency_widgets[:]:
            self.load_after_widget.remove_dependency(widget)
        if not self.is_folder_mod and hasattr(self, "init_type_combo"):
            self.init_type_combo.setCurrentText("None")
            self.init_function_edit.clear()
            self.init_delay_spin.setValue(1000)
            self.finalizer_edit.clear()
