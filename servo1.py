# servo1.py
from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
import threading

servo_bp = Blueprint('servo', __name__)

# DO NOT import from app.py here (circular import issue)
mc = None
plc_lock = threading.Lock()
connect_plc = lambda: None  # Dummy placeholder

def init_servo(shared_mc, shared_lock, shared_connect):
    global mc, plc_lock, connect_plc
    mc = shared_mc
    plc_lock = shared_lock
    connect_plc = shared_connect


def safe_read_words(start_addr, count):
    try:
        with plc_lock:
            if mc is None:
                if not connect_plc():
                    return None
            return mc.batchread_wordunits(start_addr, count)
    except Exception as e:
        print(f"❌ Servo read error: {e}")
        connect_plc()
        import time
        time.sleep(3)
        return None


def safe_write_words(start_addr, values):
    try:
        with plc_lock:
            if mc is None:
                if not connect_plc():
                    return False
            mc.batchwrite_wordunits(start_addr, values)
            return True
    except Exception as e:
        print(f"❌ Servo write error: {e}")
        connect_plc()
        import time
        time.sleep(3)
        return False


@servo_bp.route("/servo1")
def servo1_page():
    return render_template("station1/servo1.html")


# @servo_bp.route("/api/servo1/read", methods=["GET"])
# def read_servo_registers():
#     data = safe_read_words("D71", 20)
#     if data is not None:
#         return jsonify({"status": "ok", "values": data})
#     else:
#         return jsonify({"status": "error", "message": "Failed to read"})


@servo_bp.route("/api/servo1/read", methods=["GET"])
def read_servo_registers():
    data = safe_read_words("D71", 20)
    if data is not None:
        # Swap and merge D76 and D77 for position
        position = (data[6] << 16) + data[5]  # swapped: D77 high, D76 low
        # Swap and merge D78 and D79 for speed
        speed = (data[8] << 16) + data[7]  # swapped: D79 high, D78 low
        
        # Replace the original values in the list or add new keys in response
        # I suggest adding these as separate keys in the JSON response for clarity:
        response = {
            "status": "ok",
            "values": data,
            "position": position,
            "speed": speed
        }
        return jsonify(response)
    else:
        return jsonify({"status": "error", "message": "Failed to read"})





@servo_bp.route("/api/servo1/write", methods=["POST"])
def write_servo_registers():
    try:
        payload = request.get_json()
        values = payload.get("values")

        if not isinstance(values, list) or len(values) != 20:
            return jsonify({"status": "error", "message": "Expected 20 integers in 'values'"})

        success = safe_write_words("D51", values)
        if success:
            return jsonify({"status": "ok", "written": values})
        else:
            return jsonify({"status": "error", "message": "Failed to write"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
