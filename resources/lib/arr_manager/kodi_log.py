# SPDX-License-Identifier: GPL-3.0-or-later
import traceback


class KodiLogger:
    def __init__(self, debug=False):
        import xbmc
        self.xbmc = xbmc
        self.debug_enabled = debug

    def _write(self, message, *args):
        if args:
            message = message % args
        self.xbmc.log(f"[Managarr] {message}", self.xbmc.LOGDEBUG)

    def debug(self, message, *args):
        if self.debug_enabled:
            self._write(message, *args)

    def info(self, message, *args):
        self._write(message, *args)

    def warning(self, message, *args):
        self._write(message, *args)

    def error(self, message, *args):
        self._write(message, *args)

    def exception(self, message):
        self._write("%s\n%s", message, traceback.format_exc())
