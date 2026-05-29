import json
import logging
import io


def test_json_formatter_emits_valid_json():
    """JsonFormatter must emit a valid JSON line with ts, level, logger, msg fields."""
    from brn_daemon.main import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)

    assert "ts" in data
    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert data["msg"] == "hello world"
    assert "exc" not in data or data["exc"] is None


def test_json_formatter_includes_exc_on_exception():
    """JsonFormatter must include exc field when exception info is present."""
    import traceback
    from brn_daemon.main import JsonFormatter

    formatter = JsonFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        import sys
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test.logger",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="something failed",
        args=(),
        exc_info=exc_info,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["exc"] is not None
    assert "ValueError" in data["exc"]
