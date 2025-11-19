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

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
FLASK_HOST = os.environ.setdefault("FLASK_HOST", "0.0.0.0")
FLASK_PORT = 5000
FLASK_DEBUG = True

DEFAULT_TIMEOUT = 2
esam_endpoint = "http://192.168.11.25:8088"
api_endpoint = "http://192.168.11.25/api/v1/"

_id = 0
def get_id():
    global _id
    _id += 1
    return _id

def str_to_hex(s: str) -> str:
    return s.encode('utf-8').hex()

def get_template_scte():
    # TEMPLATE SCTE
    template = '/DBDAAAAAAAAAP/wAQZ/ADECL0NVRUkAAAABf/8AAAAAPA4bZm10PWZ1bGxzY3JlZW4mYXVkPWNyZWF0aXZlMAAAlisXEw=='
    return template

def create_scte_35(upid: str, duration: float):
    template = get_template_scte()
    seg_duration = round(duration * 90000)
    cue = threefive.Cue(template)
    seg = cue.descriptors[0]
    # Modify SCTE
    if type(seg) is threefive.SegmentationDescriptor:
       seg.segmentation_event_id = str(get_id())
       seg.segmentation_upid = upid
       seg.segmentation_upid_length = len(upid)

       seg.segmentation_duration = duration
       print(seg.segmentation_duration)
    return cue.base64()

def send_scte(endpoint, stream_id, scte):
    u = str(uuid.uuid4())
    utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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
    print(xml)
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
    
@app.route("/", methods=['GET'])
def index():
    return render_template('index.html')

@app.route("/api/scte", methods=['POST'])
def api_scte():
    # GET VARIABLES FROM POST REQUEST
    if not request.is_json:
        return jsonify({"error": "invalid_content_type", "expected": "application/json"}), 400
    
    payload = request.get_json()

    # Fields
    endpoint = payload.get("endpoint") or esam_endpoint # Optional, else will use esam_endpoint
    stream_id = payload.get("stream_id")
    upid = payload.get("upid")
    duration = payload.get("duration") or 60

    # Validation
    if not stream_id:
        return jsonify({"error": "missing_or_invalid", "field": "stream_id"}), 400
    
    # CREATE SCTE-35 BYTES
    scte = create_scte_35(upid, duration)
    print(scte)

    # CREATE XOS API CALL
    response = send_scte(endpoint, stream_id, scte)

    # ERROR HANDLING
    if type(response) == requests.exceptions.ConnectTimeout:
        return jsonify({"status": "ConnectTimeout", "response": str(response)}), 400
    
    if type(response) == requests.exceptions.ConnectionError:
        return jsonify({"status": "ConnectionError", "response": str(response)}), 400
    
    if type(response) == requests.exceptions.InvalidSchema:
        return jsonify({"status": "InvaidSchema", "response": str(response)}), 400

    return jsonify({"status": "ok", "response": str(response)}), 200

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

if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG, host=FLASK_HOST, port=FLASK_PORT)