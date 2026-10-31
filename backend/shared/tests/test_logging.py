import json
import logging

from procurehub_common.logging import JsonFormatter, request_id_var


def _line(**extra):
    rec = logging.LogRecord("t", logging.WARNING, "f.py", 1, "something happened", (), None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return json.loads(JsonFormatter("demo-service").format(rec))


def test_log_lines_are_json_with_the_core_fields():
    token = request_id_var.set("trace-1")
    try:
        out = _line(event="thing_done", approval_id="a1")
    finally:
        request_id_var.reset(token)
    assert out["level"] == "WARNING" and out["service"] == "demo-service" and out["message"] == "something happened" and out["request_id"] == "trace-1"
    assert out["event"] == "thing_done" and out["approval_id"] == "a1" and out["ts"].endswith("+00:00")


def test_extra_fields_can_never_overwrite_core_fields():
    # a field called "level" once replaced the severity with a number and broke filtering by severity
    out = _line(level=2, service="other", message="spoofed", request_id="x", ts="never")
    assert out["level"] == "WARNING" and out["service"] == "demo-service" and out["message"] == "something happened" and out["ts"] != "never" and out["request_id"] == "-"
    assert out["extra_level"] == 2 and out["extra_service"] == "other" and out["extra_request_id"] == "x" and out["extra_ts"] == "never"
