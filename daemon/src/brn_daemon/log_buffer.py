import logging
from collections import deque
from datetime import datetime


class LogBuffer:
    MAX_LINES = 500

    def __init__(self, max_lines: int = 500) -> None:
        self._buf: deque[dict] = deque(maxlen=max_lines)

    def append(self, record: logging.LogRecord) -> None:
        level = self._normalise(record.levelno)
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        self._buf.append({"ts": ts, "level": level, "msg": record.getMessage()})

    def get(self, level: str | None = None, limit: int = 100) -> list[dict]:
        lines = list(self._buf)
        if level == "WARNING":
            lines = [l for l in lines if l["level"] in ("WARNING", "ERROR")]
        elif level == "ERROR":
            lines = [l for l in lines if l["level"] == "ERROR"]
        return lines[-limit:]

    @staticmethod
    def _normalise(levelno: int) -> str:
        if levelno >= logging.ERROR:
            return "ERROR"
        if levelno >= logging.WARNING:
            return "WARNING"
        if levelno >= logging.INFO:
            return "INFO"
        return "DEBUG"


class LogBufferHandler(logging.Handler):
    def __init__(self, buf: LogBuffer) -> None:
        super().__init__()
        self._buf = buf

    # Loggers whose INFO/DEBUG messages are internal chatter we don't want
    _SUPPRESSED_INFO_LOGGERS = {"LiteLLM", "litellm", "httpx", "httpcore", "openai"}

    def emit(self, record: logging.LogRecord) -> None:
        try:
            root = record.name.split(".")[0]
            if record.levelno < logging.WARNING and root in self._SUPPRESSED_INFO_LOGGERS:
                return
            self._buf.append(record)
        except Exception:
            self.handleError(record)


# Module-level singleton — imported by routes and main.py
log_buffer = LogBuffer()
