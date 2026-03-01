import logging
from brn_daemon.log_buffer import LogBuffer, LogBufferHandler, log_buffer


def test_buffer_appends_and_gets():
    buf = LogBuffer()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello world", args=(), exc_info=None
    )
    buf.append(record)
    lines = buf.get()
    assert len(lines) == 1
    assert lines[0]["msg"] == "hello world"
    assert lines[0]["level"] == "INFO"
    assert len(lines[0]["ts"]) == 8  # "HH:MM:SS"


def test_buffer_level_filter():
    buf = LogBuffer()
    for level, msg in [
        (logging.INFO, "info msg"),
        (logging.WARNING, "warn msg"),
        (logging.ERROR, "error msg"),
    ]:
        record = logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None
        )
        buf.append(record)

    warnings_and_errors = buf.get(level="WARNING")
    assert len(warnings_and_errors) == 2
    assert all(l["level"] in ("WARNING", "ERROR") for l in warnings_and_errors)

    errors_only = buf.get(level="ERROR")
    assert len(errors_only) == 1
    assert errors_only[0]["level"] == "ERROR"


def test_buffer_limit():
    buf = LogBuffer()
    for i in range(20):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=f"msg {i}", args=(), exc_info=None
        )
        buf.append(record)
    lines = buf.get(limit=5)
    assert len(lines) == 5
    # Should return the most recent 5
    assert lines[-1]["msg"] == "msg 19"


def test_buffer_max_lines_circular():
    buf = LogBuffer(max_lines=5)
    for i in range(10):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=f"msg {i}", args=(), exc_info=None
        )
        buf.append(record)
    lines = buf.get()
    assert len(lines) == 5
    # Oldest should be gone, newest retained
    msgs = [l["msg"] for l in lines]
    assert "msg 0" not in msgs
    assert "msg 9" in msgs


def test_buffer_level_normalisation():
    buf = LogBuffer()
    for level, expected in [
        (logging.DEBUG, "DEBUG"),
        (logging.INFO, "INFO"),
        (logging.WARNING, "WARNING"),
        (logging.ERROR, "ERROR"),
        (logging.CRITICAL, "ERROR"),
    ]:
        record = logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg="x", args=(), exc_info=None
        )
        buf.append(record)
    lines = buf.get()
    levels = [l["level"] for l in lines]
    assert "DEBUG" in levels
    assert "INFO" in levels
    assert "WARNING" in levels
    assert levels.count("ERROR") == 2  # ERROR + CRITICAL both map to ERROR


def test_handler_writes_to_buffer():
    buf = LogBuffer()
    handler = LogBufferHandler(buf)
    logger = logging.getLogger("test_handler")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.info("via handler")
    logger.removeHandler(handler)
    lines = buf.get()
    assert any(l["msg"] == "via handler" for l in lines)


def test_module_level_singleton_exists():
    assert log_buffer is not None
    assert isinstance(log_buffer, LogBuffer)
