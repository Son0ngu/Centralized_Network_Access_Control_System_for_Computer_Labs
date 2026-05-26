"""Socket.IO event registration."""

import logging

from flask import request

from time_utils import now_iso

logger = logging.getLogger(__name__)


def register_socketio_events(socketio) -> None:
    """Register Socket.IO events."""

    @socketio.on("connect")
    def handle_connect():
        logger.info(f"Client connected: {request.sid} at {now_iso()}")
        socketio.emit(
            "server_message",
            {
                "type": "welcome",
                "message": "Connected to Firewall Controller",
                "timestamp": now_iso(),
            },
            room=request.sid,
        )

    @socketio.on("disconnect")
    def handle_disconnect():
        logger.info(f"Client disconnected: {request.sid} at {now_iso()}")

    @socketio.on("ping")
    def handle_ping(data):
        logger.debug(f"Ping received from {request.sid}")
        socketio.emit(
            "pong",
            {"timestamp": now_iso(), "client_data": data},
            room=request.sid,
        )
