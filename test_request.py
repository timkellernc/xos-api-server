import requests
response = None
if False:
    response = requests.post(
        "http://127.0.0.1:5000/api/scte",
        json = {
            "stream_id": "station1",
            "upid": "fmt=pip&aud=creative"
        },
        headers={"Content-Type": "application/json"}
        )
if True:
    response = requests.get("http://127.0.0.1:5000/api/esam-endpoint")

if True:
    response = requests.post(
        "http://127.0.0.1:5000/api/esam-endpoint",
        json = {
            "endpoint": "http://127.0.0.1:8088"
        },
        headers={"Content-Type": "application/json"}
        )
print(response.text, response.status_code)