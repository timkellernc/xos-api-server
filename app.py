"""
DIRTVision XOS API Server

Triggers API calls to XOS server more easily because their api is complicated

"""


from flask import Flask, request, jsonify, abort, render_template
import os
from datetime import datetime, timedelta, timezone
import json
import time
import uuid
import requests
import threefive
from enum import Enum
import random
import socket
import struct
import threading

# NTP Sync Variables
time_offset_seconds = 0
SYNC_INTERVAL_MINUTES = 60

def update_time_offset():
    global time_offset_seconds
    host = "pool.ntp.org"
    port = 123
    buf = 1024
    address = (host, port)
    msg = b'\x1b' + 47 * b'\0'
    
    # reference time (in seconds since 1900-01-01 00:00:00)
    TIME1970 = 2208988800 
    
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(3.0)
    try:
        request_time = time.time()
        client.sendto(msg, address)
        msg, _ = client.recvfrom(buf)
        response_time = time.time()
        
        # t is time in seconds since 1900
        t = struct.unpack("!12I", msg)[10]
        ntp_time = t - TIME1970
        
        # Calculate offset accounting roughly for half the network round-trip
        network_delay = (response_time - request_time) / 2
        
        # Offset is NTP true time minus local system time
        time_offset_seconds = (ntp_time - network_delay) - time.time()
        print(f"[*] NTP Sync successful. Offset: {time_offset_seconds:.3f}s")
    except Exception as e:
        print(f"[*] NTP Sync failed: {e}")
    finally:
        client.close()

def sync_time_worker():
    while True:
        update_time_offset()
        time.sleep(SYNC_INTERVAL_MINUTES * 60)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
FLASK_HOST = os.environ.setdefault("FLASK_HOST", "0.0.0.0")
FLASK_PORT = 80
FLASK_DEBUG = True

DEFAULT_TIMEOUT = 2
esam_endpoint = "http://192.168.11.22:8088"
api_endpoint = "http://192.168.11.22/api/v1/"

# UPIDs
UPID_FS = ""
UPID_PIP = "fmt=pip"
UPID_L = "fmt=squeezeBack"

# Presets
presets = [
    { "title": "World of Outlaws", "stream_id": "wooscs", "color": "#3b82f6" },
    { "title": "Late Models", "stream_id": "woolms", "color": "#10b981" },
    { "title": "Super DIRTcar", "stream_id": "sdcs", "color": "#f59e0b" },
    { "title": "ASCS", "stream_id": "ascs", "color": "#ef4444" }
]

_id = random.randint(0, 500) * 1000
def get_id():
    global _id
    _id += 1
    return _id

def str_to_hex(s: str) -> str:
    return s.encode('utf-8').hex()

def get_template_scte():
    # TEMPLATE SCTE
    template = '/DBIAAAAAyiYAP/wBQb+iJjvJgAyAjBDVUVJAAFDjn//AABST/0OHGZtdD1mdWxsc2NyZWVuJmF1ZD11bmRlZmluZWQwAABmJ5RF'
    return template

def create_scte_35(upid: str, duration: float):
    template = get_template_scte()
    cue = threefive.Cue(template)
    seg = cue.descriptors[0]
    # Modify SCTE
    if type(seg) is threefive.SegmentationDescriptor:
       seg.segmentation_event_id = str(get_id())
       # Change Segmentation type id to 48 or 0x30
       seg.segmentation_upid = upid
       seg.segmentation_upid_length = len(upid)

       seg.segmentation_duration = duration + 1

    cue.command.time_specified_flag = True
    cue.command.pts_time = 0.1

    return cue.base64()

def send_scte(endpoint, stream_id, scte):
    u = str(uuid.uuid4())
    utc_now = datetime.now(timezone.utc) + timedelta(seconds=time_offset_seconds)
    utc_time = utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # TEMPLATE XML
    xml = f"""<SignalProcessingNotification xmlns="urn:cablelabs:iptvservices:esam:xsd:signal:1"
                xmlns:ns6="urn:cablelabs:iptvservices:esam:xsd:manifest:1"
                xmlns:ns5="urn:cablelabs:iptvservices:esam:xsd:common:1"
                xmlns:ns2="urn:cablelabs:md:xsd:core:3.0"
                xmlns:ns4="urn:cablelabs:md:xsd:content:3.0"
                xmlns:ns3="urn:cablelabs:md:xsd:signaling:3.0">
                <ResponseSignal action="create" acquisitionPointIdentity="{stream_id}" acquisitionSignalID="{u}">
                    <ns3:UTCPoint utcPoint="{utc_time}"/>
                    <ns3:BinaryData signalType="SCTE35">{scte}</ns3:BinaryData>
                </ResponseSignal>
            </SignalProcessingNotification>"""
    print(scte)
    try:
        r = requests.post(
            f"{endpoint}",
            data=xml,
            headers={"Content-Type": "text/xml"},
            timeout=DEFAULT_TIMEOUT,
            verify=False
        )
        return r
    except requests.exceptions.ConnectTimeout as e:
        return e
    except requests.exceptions.ConnectionError as e:
        return e
    except requests.exceptions.InvalidSchema as e:
        return e
    except Exception as e:
        print(type(e))
        return e
    
def load_presets():
    global presets
    if os.path.exists("presets.json"):
        try:
            with open("presets.json", "r") as f:
                presets = json.load(f)
        except Exception:
            pass
    presets.sort(key=lambda x: str(x.get("title", "")).lower())

def save_presets():
    presets.sort(key=lambda x: str(x.get("title", "")).lower())
    with open("presets.json", "w") as f:
        json.dump(presets, f)

@app.route("/api/presets", methods=['GET'])
def api_presets():
    return jsonify(presets)

@app.route("/api/presets/add", methods=['POST'])
def api_presets_add():
    if not request.is_json:
        return jsonify({"error": "invalid_content_type", "expected": "application/json"}), 400
    
    payload = request.get_json()
    title = payload.get("title")
    stream_id = payload.get("stream_id")
    color = payload.get("color")
    if not title or not stream_id:
        return jsonify({"error": "missing_or_invalid", "field": "title_or_stream_id"}), 400
    
    for p in presets:
        if p.get("title") == title:
            p["stream_id"] = stream_id
            if color:
                p["color"] = color
            save_presets()
            return jsonify(presets)
            
    presets.append({"title": title, "stream_id": stream_id, "color": color or "#3b82f6"})
    save_presets()
    return jsonify(presets)

@app.route("/api/presets/remove", methods=['POST'])
def api_presets_remove():
    global presets
    if not request.is_json:
        return jsonify({"error": "invalid_content_type", "expected": "application/json"}), 400
    
    payload = request.get_json()
    title = payload.get("title")
    if not title:
        return jsonify({"error": "missing_or_invalid", "field": "title"}), 400
    
    presets = [p for p in presets if p.get("title") != title]
    save_presets()
    return jsonify(presets)

@app.route("/api/upids", methods=['GET'])
def api_upids():
    return jsonify({"upid_fs": UPID_FS, "upid_pip": UPID_PIP, "upid_l": UPID_L})

@app.route("/", methods=['GET'])
def index():
    return render_template('index.html')

@app.route("/client", methods=['GET'])
def client():
    return render_template('client.html')


@app.route("/api/scte", methods=['POST'])
def api_scte():
    # GET VARIABLES FROM POST REQUEST
    if not request.is_json:
        return jsonify({"error": "invalid_content_type", "expected": "application/json"}), 400
    
    payload = request.get_json()

    # Fields
    endpoint = payload.get("endpoint") or esam_endpoint # Optional, else will use esam_endpoint
    stream_id = payload.get("stream_id")
    upid = payload.get("upid") or ""
    duration = payload.get("duration") or 60

    # Validation
    if not stream_id:
        return jsonify({"error": "missing_or_invalid", "field": "stream_id"}), 400
    
    # CREATE SCTE-35 BYTES
    scte = create_scte_35(upid, duration)
    # print(scte)

    # CREATE XOS API CALL
    response = send_scte(endpoint, stream_id, scte)

    # ERROR HANDLING
    if type(response) == requests.exceptions.ConnectTimeout:
        return jsonify({"status": "ConnectTimeout", "response": str(response)}), 400
    
    if type(response) == requests.exceptions.ConnectionError:
        return jsonify({"status": "ConnectionError", "response": str(response)}), 400
    
    if type(response) == requests.exceptions.InvalidSchema:
        return jsonify({"status": "InvaidSchema", "response": str(response)}), 400

    if response.status_code == 503:
        print("Error: Invalid Stream ID")
        return jsonify("Invalid Stream ID"), 404
    
    if not upid:
        upid = "fmt=interstitial"
    
    timeStr = (datetime.now(timezone.utc) + timedelta(seconds=time_offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Sent {upid} {duration} to {stream_id} at {timeStr}")
    return jsonify({"status": "OK", "scte": str(scte), "time": timeStr}), response.status_code

@app.route("/api/esam-endpoint", methods=['GET', 'POST'])
def api_default_endpoint():
    global esam_endpoint
    if request.method == "POST":

        # GET VARIABLES FROM POST REQUEST
        if not request.is_json:
            return jsonify({"error": "invalid_content_type", "expected": "application/json"}), 400
        
        payload = request.get_json()

        # Fields
        endpoint = payload.get("endpoint")

        # Verify
        if not endpoint:
            return jsonify({"error": "missing_or_invalid", "field": "endpoint"}), 400
        
        # Modify
        esam_endpoint = endpoint

        # Return
        return jsonify({"status": "ok", "endpoint": esam_endpoint}), 200
    
    return jsonify({"endpoint": esam_endpoint}), 200

def startup():
    load_presets()
    ntp_thread = threading.Thread(target=sync_time_worker, daemon=True)
    ntp_thread.start()

# Initialize background tasks and load data
startup()

if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG, host=FLASK_HOST, port=FLASK_PORT)