from servo1 import servo_bp
from servo1 import init_servo  # <-- Added import here

from flask import Flask, render_template, jsonify, request
import pymcprotocol
import threading
import time
from datetime import datetime

app = Flask(__name__)
app.register_blueprint(servo_bp)  # Register the blueprint here

# PLC connection config
PLC_IP = "192.168.3.250"
PLC_PORT = 5000

# Shared global data storage for PLC values
plc_data = {
    "station1": {"D0": 0, "D1": 0, "D2": 0, "Bits_M501_600": [], "Timestamp": None},
    "station2": {"D10": 0, "D11": 0, "D12": 0, "Timestamp": None},
    "station3": {"D20": 0, "D21": 0, "D22": 0, "Timestamp": None},
    "station4": {"D30": 0, "D31": 0, "D32": 0, "Timestamp": None},
}

plc_lock = threading.Lock()
data_lock = threading.Lock()

mc = None

station_d_bases = {
    "station1": "D0",
    "station2": "D10",
    "station3": "D20",
    "station4": "D30",
}

station_keys = {
    "station1": ["D0", "D1", "D2"],
    "station2": ["D10", "D11", "D12"],
    "station3": ["D20", "D21", "D22"],
    "station4": ["D30", "D31", "D32"],
}

station_bit_maps = {
    "station1": {"start": "M100", "stop": "M101", "reset": "M102", "servo_on": "M103"},
    "station2": {"start": "M110", "stop": "M111", "reset": "M112", "servo_on": "M113"},
    "station3": {"start": "M120", "stop": "M121", "reset": "M122", "servo_on": "M123"},
    "station4": {"start": "M130", "stop": "M131", "reset": "M132", "servo_on": "M133"},
}

custom_button_bits = {
    "button1": "M531",
    "button2": "M532",
    "button3": "M533",
    "button4": "M534",
    "button5": "M535",
    "button6": "M536",
    "button7": "M537",
    "button8": "M538",
    "button9": "M539",
    "button10": "M540",
    "button11": "M541",
    "button12": "M542",
    "button13": "M543",
    "button14": "M544",
    "button15": "M545",
}


def connect_plc():
    global mc
    try:
        if mc:
            try:
                mc.close()
            except:
                pass
        mc = pymcprotocol.Type3E()
        mc.connect(PLC_IP, PLC_PORT)
        print(f"🔌 Connected to PLC at {PLC_IP}:{PLC_PORT}")
        return True
    except Exception as e:
        print(f"❌ Failed to connect PLC: {e}")
        mc = None
        return False


def safe_read_words(address_base):
    global mc
    try:
        with plc_lock:
            if mc is None:
                if not connect_plc():
                    return None
            values = mc.batchread_wordunits(address_base, 3)
        return values
    except Exception as e:
        print(f"❌ PLC read error at {address_base}: {e}")
        connect_plc()
        time.sleep(3)  # delay after failure
        return None


def safe_read_bits(start_bit, count):
    global mc
    try:
        with plc_lock:
            if mc is None:
                if not connect_plc():
                    return None
            bits = mc.batchread_bitunits(start_bit, count)
        return bits
    except Exception as e:
        print(f"❌ PLC bit read error at {start_bit}: {e}")
        connect_plc()
        time.sleep(3)  # delay after failure
        return None


def safe_write(bit_addr):
    global mc
    try:
        with plc_lock:
            if mc is None:
                if not connect_plc():
                    return
            mc.batchwrite_bitunits(bit_addr, [1])
            time.sleep(1)
            mc.batchwrite_bitunits(bit_addr, [0])
    except Exception as e:
        print(f"❌ PLC write error at {bit_addr}: {e}")
        connect_plc()
        time.sleep(3)  # delay after failure


def poll_plc():
    global plc_data
    while True:
        for station, base_addr in station_d_bases.items():
            word_values = safe_read_words(base_addr)
            if word_values and len(word_values) == 3:
                with data_lock:
                    keys = station_keys[station]
                    plc_data[station].update({
                        keys[0]: word_values[0],
                        keys[1]: word_values[1],
                        keys[2]: word_values[2],
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
            else:
                print(f"⚠️ Skipped update for {station} due to word read failure")

        # Read M501–M600 bits for station1
        bits = safe_read_bits("M501", 100)
        if bits and len(bits) == 100:
            with data_lock:
                plc_data["station1"]["Bits_M501_600"] = bits
        else:
            print("⚠️ Skipped update for bits M501–M600 due to read failure")

        time.sleep(3)  # Increased sleep to reduce PLC load and connection resets


connect_plc()

# <-- ADD init_servo call here (after PLC connection) --
init_servo(mc, plc_lock, connect_plc)

threading.Thread(target=poll_plc, daemon=True).start()

# ------------------ ROUTES ------------------ #

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/station1")
def station1():
    return render_template("station1.html")


@app.route("/station2")
def station2():
    return render_template("station2.html")


@app.route("/station3")
def station3():
    return render_template("station3.html")


@app.route("/station4")
def station4():
    return render_template("station4.html")


@app.route("/station1input")
def station1input():
    return render_template("station1/station1input.html")


@app.route("/station1output")
def station1output():
    return render_template("station1/station1output.html")


@app.route("/api/<station>/data")
def station_data(station):
    if station not in plc_data:
        return jsonify({"status": "error", "message": "Invalid station"}), 404

    with data_lock:
        data = plc_data[station].copy()

    if data["Timestamp"]:
        response = {"status": "ok", **data}

        # Correctly map M501–M515 to bits1 and M516–M530 to bits2 for station1
        if station == "station1":
            bits = data.get("Bits_M501_600", [])
            if len(bits) >= 30:
                response["bits1"] = bits[0:15]     # M501 to M515
                response["bits2"] = bits[15:30]    # M516 to M530
            else:
                response["bits1"] = [0] * 15
                response["bits2"] = [0] * 15

        return jsonify(response)
    else:
        return jsonify({"status": "error", "message": "No data yet"})


@app.route("/api/<station>/control", methods=["POST"])
def station_control(station):
    if station not in station_bit_maps:
        return jsonify({"status": "error", "message": "Invalid station"}), 404

    data = request.json
    if not data or "action" not in data:
        return jsonify({"status": "error", "message": "Missing action parameter"}), 400

    action = data.get("action")

    # Check station-specific control bits
    bit_map = station_bit_maps[station]
    addr = bit_map.get(action)

    # Then check global button mapping
    if not addr:
        addr = custom_button_bits.get(action)

    if not addr:
        return jsonify({"status": "error", "message": "Invalid action"}), 400

    threading.Thread(target=safe_write, args=(addr,), daemon=True).start()
    return jsonify({"status": "ok", "action": action})


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
