"""
Dialog for collecting user input during profile installation.

When a community profile includes `user_prompts`, this dialog is shown
to let the user configure required settings before installation completes.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from me3_manager.utils.translator import tr


class UserPromptsDialog(QDialog):
    """Dialog to collect user input for profile configuration settings."""

    def __init__(
        self,
        prompts: list[dict[str, Any]],
        profile_description: str = "",
        parent: QWidget | None = None,
    ):
        """
        Initialize the dialog.

        Args:
            prompts: List of prompt definitions, each containing:
                - key: The config key (e.g., "PASSWORD.cooppassword")
                - label: Display label for the field
                - description: Optional help text
                - type: "string", "password", "number", or "boolean" (default: "string")
                - required: Whether the field is required (default: True)
                - default: Default value (optional)
                - config: Path to the config file this belongs to
            profile_description: Optional description of the profile
            parent: Parent widget
        """
        super().__init__(parent)
        self.prompts = prompts
        self.profile_description = profile_description
        self.inputs: dict[str, QWidget] = {}

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle(tr("user_prompts_dialog_title"))
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)

        # Description
        desc_label = QLabel(tr("user_prompts_dialog_description"))
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Profile description if provided
        if self.profile_description:
            profile_desc = QLabel(self.profile_description)
            profile_desc.setWordWrap(True)
            profile_desc.setStyleSheet(
                "color: #888; font-style: italic; margin: 5px 0;"
            )
            layout.addWidget(profile_desc)

        # Scroll area for prompts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_widget = QWidget()
        form_layout = QFormLayout(scroll_widget)
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # Create input fields for each prompt
        for prompt in self.prompts:
            key = prompt.get("key", "")
            label = prompt.get("label", key)
            description = prompt.get("description", "")
            prompt_type = prompt.get("type", "string").lower()
            required = prompt.get("required", True)
            default = prompt.get("default", "")

            # Create label with required indicator
            label_text = f"{label}" + (" *" if required else "")

            # Create appropriate input widget
            if prompt_type == "boolean":
                widget = QCheckBox()
                widget.setChecked(bool(default))
            elif prompt_type == "number":
                widget = QSpinBox()
                widget.setRange(-999999, 999999)
                if default:
                    try:
                        widget.setValue(int(default))
                    except (ValueError, TypeError):
                        pass
            else:  # string or password
                widget = QLineEdit()
                if default:
                    widget.setText(str(default))
                if prompt_type == "password":
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
                widget.setPlaceholderText(description if description else label)

            # Add tooltip with description
            if description:
                widget.setToolTip(description)

            form_layout.addRow(label_text, widget)
            self.inputs[key] = widget

            # Add description label if provided (for non-text fields)
            if description and prompt_type in ("boolean", "number"):
                desc_hint = QLabel(description)
                desc_hint.setStyleSheet(
                    "color: #888; font-size: 11px; margin-left: 5px;"
                )
                desc_hint.setWordWrap(True)
                form_layout.addRow("", desc_hint)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)

        # Required fields note
        if any(p.get("required", True) for p in self.prompts):
            note = QLabel(tr("user_prompts_required_note"))
            note.setStyleSheet("color: #888; font-size: 11px;")
            layout.addWidget(note)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _validate_and_accept(self):
        """Validate required fields and accept if valid."""
        missing = []

        for prompt in self.prompts:
            key = prompt.get("key", "")
            label = prompt.get("label", key)
            required = prompt.get("required", True)
            prompt_type = prompt.get("type", "string").lower()

            if not required:
                continue

            widget = self.inputs.get(key)
            if not widget:
                continue

            # Check if value is empty
            if prompt_type == "boolean":
                # Booleans are always "filled"
                continue
            elif prompt_type == "number":
                # SpinBoxes always have a value
                continue
            else:
                # Text fields
                if isinstance(widget, QLineEdit) and not widget.text().strip():
                    missing.append(label)

        if missing:
            QMessageBox.warning(
                self,
                tr("user_prompts_required_error_title"),
                tr("user_prompts_required_error")
                + "\n\n"
                + "\n".join(f"• {m}" for m in missing),
            )
            return

        self.accept()

    def get_values(self) -> dict[str, Any]:
        """
        Get the collected values.

        Returns:
            Dictionary mapping config keys to their values.
            Values are typed appropriately (str, int, bool).
        """
        values = {}

        for prompt in self.prompts:
            key = prompt.get("key", "")
            prompt_type = prompt.get("type", "string").lower()

            widget = self.inputs.get(key)
            if not widget:
                continue

            if prompt_type == "boolean":
                values[key] = widget.isChecked()
            elif prompt_type == "number":
                values[key] = widget.value()
            else:
                text = widget.text().strip()
                if text:  # Only include non-empty values
                    values[key] = text

        return values

    def get_values_by_config(self) -> dict[str, dict[str, Any]]:
        """
        Get values grouped by their config file.

        Returns:
            Dictionary mapping config paths to dictionaries of key-value pairs.
        """
        result: dict[str, dict[str, Any]] = {}

        for prompt in self.prompts:
            key = prompt.get("key", "")
            config = prompt.get("config", "")
            prompt_type = prompt.get("type", "string").lower()

            if not config:
                continue

            widget = self.inputs.get(key)
            if not widget:
                continue

            if config not in result:
                result[config] = {}

            if prompt_type == "boolean":
                result[config][key] = 1 if widget.isChecked() else 0
            elif prompt_type == "number":
                result[config][key] = widget.value()
            else:
                text = widget.text().strip()
                if text:
                    result[config][key] = text

        return result
