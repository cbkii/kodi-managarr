# SPDX-License-Identifier: GPL-3.0-or-later
class ArrManagerError(Exception):
    """Base expected error shown to the Kodi user."""


class ConfigurationError(ArrManagerError):
    pass


class ResolutionError(ArrManagerError):
    pass


class ApiError(ArrManagerError):
    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


class SafetyError(ArrManagerError):
    pass


class BlocklistError(ArrManagerError):
    pass
