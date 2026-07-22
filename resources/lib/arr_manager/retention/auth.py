# SPDX-License-Identifier: GPL-3.0-or-later

# Dummy PIN adapter implementation
class DummyPINAuthoriser:
    def __init__(self, addon, ui):
        self.addon = addon
        self.ui = ui

    def is_configured(self) -> bool:
        return False

    def get_generation(self) -> str:
        return "no_pin_configured"

    def authorize(self, operation_name: str) -> bool:
        # Prompt user if PIN would be required
        if self.ui:
            return self.ui.confirm("Authorization Required", f"Authorize {operation_name}?")
        return True
