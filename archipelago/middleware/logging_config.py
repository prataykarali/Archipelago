import json
import logging
import time
import uuid

from flask import g, request


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "status"):
            log_data["status"] = record.status
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        return json.dumps(log_data)

def setup_logging(app):
    from archipelago.middleware.log_redaction import install_log_redaction

    install_log_redaction()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    # Remove default handlers and add our JSON handler
    app.logger.handlers = []
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def before_request():
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()

    @app.after_request
    def after_request(response):
        if not hasattr(g, 'start_time'):
            return response

        duration_ms = (time.time() - g.start_time) * 1000

        log_record = logging.LogRecord(
            name=app.logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Request processed",
            args=(),
            exc_info=None
        )
        log_record.request_id = getattr(g, "request_id", "-")
        log_record.method = request.method
        log_record.path = request.path
        log_record.status = response.status_code
        log_record.duration_ms = round(duration_ms, 2)

        app.logger.handle(log_record)
        return response
