import signal
import logging
from flask import jsonify

is_shutting_down = False
logger = logging.getLogger(__name__)

def handle_shutdown(signum, frame):
    global is_shutting_down
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    is_shutting_down = True

def setup_shutdown_handlers(app):
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    @app.before_request
    def check_shutdown():
        if is_shutting_down:
            return jsonify({"error": "Service is shutting down"}), 503
