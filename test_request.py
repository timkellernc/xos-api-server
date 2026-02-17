import requests
response = None
if True:
    response = requests.post(
        "http://127.0.0.1:5000/api/scte",
        json = {
            "stream_id": "mcr1",
            "upid": "",
            "duration": 60
        },
        headers={"Content-Type": "application/json"}
        )
if False:
    response = requests.get("http://127.0.0.1:5000/api/esam-endpoint")

if False:
    response = requests.post(
        "http://127.0.0.1:5000/api/esam-endpoint",
        json = {
            "endpoint": "http://127.0.0.1:8088"
        },
        headers={"Content-Type": "application/json"}
        )
print(response.text, response.status_code)