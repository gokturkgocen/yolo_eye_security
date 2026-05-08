# YOLO Eye: Real-time Person Detection

Local-network person detection prototype using **YOLOv8**, OpenCV and Flask.
The backend monitors a camera feed, exposes the current detection state, and
serves the latest annotated frame as a base64 snapshot.

> Public snapshot note: this repository currently contains the Python backend.
> The mobile client is described at architecture level only; it is not included
> in this public snapshot.

---

## Features

- **Real-time person detection** with YOLOv8.
- **Flask status endpoint** for local clients.
- **Snapshot endpoint** for the latest annotated frame.
- **Local-first deployment**: laptop / edge computer and phone on the same Wi-Fi.

---

## Architecture

```mermaid
graph LR
    Camera[USB/Integrated Camera] --> YOLO[Python YOLOv8 Processor]
    YOLO --> Flask[Flask Web Server]
    Flask -- "HTTP status (/status)" --> Client[Local Client]
    Flask -- "Base64 snapshot (/snapshot)" --> Client
```

---

## Setup

1. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
2. Run the server:
   ```bash
   python server.py
   ```
3. Open the local status / snapshot endpoints from a browser or client on the
   same network.

---

## Requirements

- **Python**: 3.9+
- **Network**: Both laptop and phone must be on the same Wi-Fi network.

---

## License
This project is licensed under the MIT License - see the LICENSE file for details.
