# SPDX-License-Identifier: GPL-3.0-or-later
import traceback


class KodiLogger:
    def __init__(self, debug=False):
        import xbmc
        self.xbmc = xbmc
        self.debug_enabled = debug

    def _write(self, message, level, *args):
        if args:
            message = message % args
        self.xbmc.log(f"[Managarr] {message}", level)

    def debug(self, message, *args):
        if self.debug_enabled:
            self._write(message, self.xbmc.LOGDEBUG, *args)

    def info(self, message, *args):
        self._write(message, self.xbmc.LOGINFO, *args)

    def warning(self, message, *args):
        self._write(message, self.xbmc.LOGWARNING, *args)

    def error(self, message, *args):
        self._write(message, self.xbmc.LOGERROR, *args)

    def exception(self, message):
        self._write("%s\n%s", self.xbmc.LOGERROR, message, traceback.format_exc())
