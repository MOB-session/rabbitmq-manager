import os
from flask import Flask, jsonify, render_template, request
import rabbitmq_service

# Initialize the Flask web application
app = Flask(__name__)


# -----------------------------------------------------------------------------
# Web Page Route
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    """
    Renders and serves the main single-page interface (templates/index.html).
    Contains both the 'Move' and 'Delete' management tabs.
    """
    return render_template("index.html")


# -----------------------------------------------------------------------------
# API Route: List Virtual Hosts
# -----------------------------------------------------------------------------
@app.route("/api/vhosts", methods=["GET"])
def get_vhosts():
    """
    Queries RabbitMQ Management API to discover all existing virtual hosts (vhosts).
    Returns the list of vhost names and the configured default vhost.
    """
    try:
        vhosts = rabbitmq_service.list_vhosts()
        current_default = rabbitmq_service.VHOST
        return jsonify({"success": True, "vhosts": vhosts, "default": current_default})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# -----------------------------------------------------------------------------
# API Route: List Queues in a VHost
# -----------------------------------------------------------------------------
@app.route("/api/queues", methods=["GET"])
def get_queues():
    """
    Retrieves all queues residing in the requested vhost along with their stats
    (ready message count, unacknowledged count, active consumers).
    Used to populate input autocompletion in the UI.
    """
    vhost = request.args.get("vhost", "").strip() or None
    try:
        queues = rabbitmq_service.list_queues(vhost=vhost)
        return jsonify({"success": True, "queues": queues, "vhost": vhost or rabbitmq_service.VHOST})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# -----------------------------------------------------------------------------
# API Route: Peek Messages from a Queue (Non-destructive)
# -----------------------------------------------------------------------------
@app.route("/api/messages/peek", methods=["POST"])
def peek_queue():
    """
    Safely inspects up to `limit` messages in a queue without removing them or
    altering their FIFO order. Extracts identifiers, headers, and payload previews.
    Triggered when the user clicks 'Move Selected' or 'Select Messages to Delete'.
    """
    data = request.get_json() or {}
    queue = data.get("queue", "").strip()
    vhost = data.get("vhost", "").strip() or None
    limit = int(data.get("limit", 200))

    if not queue:
        return jsonify({"success": False, "error": "Queue name is required."}), 400

    try:
        messages = rabbitmq_service.peek_messages(queue, limit=limit, vhost=vhost)
        return jsonify({
            "success": True,
            "queue": queue,
            "vhost": vhost or rabbitmq_service.VHOST,
            "messages": messages,
            "count": len(messages)
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# -----------------------------------------------------------------------------
# API Route: Move All Messages
# -----------------------------------------------------------------------------
@app.route("/api/messages/move-all", methods=["POST"])
def move_all():
    """
    Drains all messages from `from_queue` and transfers them to `to_queue` in FIFO order.
    Uses publisher confirms and manual acknowledgements to ensure zero message loss.
    """
    data = request.get_json() or {}
    from_queue = data.get("from_queue", "").strip()
    to_queue = data.get("to_queue", "").strip()
    vhost = data.get("vhost", "").strip() or None

    # Validate that both queues are provided
    if not from_queue or not to_queue:
        return jsonify({"success": False, "error": "Both source and destination queues are required."}), 400

    # Prevent infinite loop if queues are identical
    if from_queue == to_queue:
        return jsonify({"success": False, "error": "Source and destination queues must not be identical."}), 400

    try:
        result = rabbitmq_service.move_all_messages(from_queue, to_queue, vhost=vhost)
        return jsonify({"success": True, **result})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# -----------------------------------------------------------------------------
# API Route: Move Selected Messages by ID
# -----------------------------------------------------------------------------
@app.route("/api/messages/move-selected", methods=["POST"])
def move_selected():
    """
    Searches the source queue for specific message IDs and moves only the matching ones
    to the destination queue. Inspected non-matching messages are placed back at the head
    of the source queue in their original relative sequence.
    """
    data = request.get_json() or {}
    from_queue = data.get("from_queue", "").strip()
    to_queue = data.get("to_queue", "").strip()
    vhost = data.get("vhost", "").strip() or None
    message_ids = data.get("message_ids", [])

    if not from_queue or not to_queue:
        return jsonify({"success": False, "error": "Both source and destination queues are required."}), 400

    if not message_ids:
        return jsonify({"success": False, "error": "No message IDs selected to move."}), 400

    try:
        result = rabbitmq_service.move_selected_messages(from_queue, to_queue, message_ids, vhost=vhost)
        return jsonify({"success": True, **result})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# -----------------------------------------------------------------------------
# API Route: Delete Selected Messages by ID
# -----------------------------------------------------------------------------
@app.route("/api/messages/delete-selected", methods=["POST"])
def delete_selected():
    """
    Selectively removes specific message IDs from the specified queue.
    Matching messages are acknowledged without republishing (deleted from RabbitMQ),
    while non-matching messages are preserved in original order.
    """
    data = request.get_json() or {}
    queue = data.get("queue", "").strip()
    vhost = data.get("vhost", "").strip() or None
    message_ids = data.get("message_ids", [])

    if not queue:
        return jsonify({"success": False, "error": "Queue name is required."}), 400

    if not message_ids:
        return jsonify({"success": False, "error": "No message IDs selected to delete."}), 400

    try:
        result = rabbitmq_service.delete_selected_messages(queue, message_ids, vhost=vhost)
        return jsonify({"success": True, **result})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# -----------------------------------------------------------------------------
# API Route: Purge Queue (Delete All Messages)
# -----------------------------------------------------------------------------
@app.route("/api/messages/purge-queue", methods=["POST"])
def purge_queue():
    """
    Permanently purges all messages from the specified queue in the given vhost.
    """
    data = request.get_json() or {}
    queue = data.get("queue", "").strip()
    vhost = data.get("vhost", "").strip() or None

    if not queue:
        return jsonify({"success": False, "error": "Queue name is required."}), 400

    try:
        result = rabbitmq_service.purge_queue(queue, vhost=vhost)
        return jsonify({"success": True, **result})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# -----------------------------------------------------------------------------
# Server Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Read port from environment variable, default to 5000
    port = int(os.getenv("PORT", "5000"))
    # Run development server accessible locally and across the network
    app.run(host="0.0.0.0", port=port, debug=True)
