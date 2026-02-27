import cv2
import time
import threading
import socket
from flask import Flask, request, jsonify, Response
from ultralytics import YOLO

# Global alert state
alert_active = False
connected_clients = 0
latest_frame = None
frame_lock = threading.Lock()

# Initialize Flask App
app = Flask(__name__)

def generate_frames():
    """Generator function that continuously yields JPEG frames."""
    global latest_frame
    while True:
        with frame_lock:
            if latest_frame is None:
                frame = None
            else:
                ret, buffer = cv2.imencode('.jpg', latest_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                frame = buffer.tobytes() if ret else None
                
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        # Sleep tight to avoid 100% CPU lock on the generator and limit framerate
        time.sleep(0.08)  # ~12 FPS stream limit

import base64

@app.route('/snapshot')
def get_snapshot():
    """Returns a single base64 encoded frame. Polling this is more stable than MJPEG on mobile."""
    global latest_frame
    with frame_lock:
        if latest_frame is None:
            return jsonify({"status": "error", "message": "No frame"}), 404
        
        # Encode to JPEG with lower quality for faster transmission
        ret, buffer = cv2.imencode('.jpg', latest_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 40])
        if not ret:
            return jsonify({"status": "error", "message": "Encode failed"}), 500
            
        b64_frame = base64.b64encode(buffer).decode('utf-8')
        
    response = jsonify({"status": "success", "image": b64_frame})
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response, 200

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    # Allow CORS so mobile doesn't block it
    response = Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

@app.route('/stream')
def stream_page():
    """Stream wrapper to prevent black screen issues on some mobile WebViews."""
    return """
    <html>
      <body style="margin:0;background:black;display:flex;justify-content:center;align-items:center;">
        <img src="/video_feed" style="width:100%;height:auto;">
      </body>
    </html>
    """

@app.route('/connect', methods=['POST', 'OPTIONS'])
def connect_client():
    if request.method == 'OPTIONS':
        # Provide CORS headers
        response = jsonify({'status': 'ok'})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        return response, 200

    global connected_clients
    client_ip = request.remote_addr
    
    # Simple way to prevent duplicate counting:
    if not hasattr(app, "tracked_ips"):
        app.tracked_ips = set()
        
    if client_ip not in app.tracked_ips:
        app.tracked_ips.add(client_ip)
        connected_clients += 1
        print(f"\n[SERVER] Yeni bir mobil cihaz sunucuya baglandi ({client_ip}). Toplam: {connected_clients}\n")
    
    response = jsonify({"status": "success", "message": "Connected"})
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response, 200

@app.route('/status', methods=['GET', 'OPTIONS'])
def get_status():
    if request.method == 'OPTIONS':
        # Provide CORS headers for parsing JSON polling
        response = jsonify({'status': 'ok'})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        return response, 200

    global alert_active
    response = jsonify({"alert": alert_active})
    response.headers.add("Access-Control-Allow-Origin", "*")
    
    # Reset alert after someone reads it
    if alert_active:
        alert_active = False
        
    return response, 200

def run_flask():
    # Run flask on port 5000, listening on all interfaces
    # Disable reloader so it doesn't run twice and block the main thread
    # threaded=True is required so multiple requests (or a slow request) don't block others
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)

def get_local_ip():
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except:
        return "127.0.0.1"

def main():
    print("="*60)
    print(f"YOLO + LOKAL BILDIRIM SUNUCUSU")
    print(f"Mobil uygulamadan 'Laptop IP Adresi' olarak sunu girin: {get_local_ip()}")
    print("="*60)

    # Start Flask server in a background thread
    server_thread = threading.Thread(target=run_flask, daemon=True)
    server_thread.start()

    print("[YOLO] Model yukleniyor...")
    model = YOLO("yolov8n.pt") 
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Hata: Kamera açılamadı!")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    prev_time = 0
    last_notification_time = 0
    NOTIFICATION_COOLDOWN = 15

    print("[YOLO] Kamera acildi! Cikmak icin kameranin uzerindeyken 'q' tusuna basin.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Hata: Goruntu alinamadi!")
            break
            
        results = model.predict(frame, imgsz=320, conf=0.5, verbose=False)
        annotated_frame = results[0].plot()
        
        person_detected = False
        for box in results[0].boxes:
            class_id = int(box.cls[0])
            if class_id == 0:  # 0 -> Person
                person_detected = True
                break
                
        current_time = time.time()
                
        if person_detected:
            cv2.putText(annotated_frame, "UYARI: INSAN TESPIT EDILDI!", (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3, cv2.LINE_AA)
            cv2.rectangle(annotated_frame, (0, 0), (640, 70), (0, 0, 255), 4)
            
            # Send notification if cooldown has passed
            if (current_time - last_notification_time) > NOTIFICATION_COOLDOWN:
                if connected_clients > 0:
                    print("\n[YOLO] Insan tespit edildi! Alert hazirlandi (Telefon okumasi bekleniyor)...")
                    global alert_active
                    alert_active = True
                    last_notification_time = current_time

        fps = 1 / (current_time - prev_time) if (current_time - prev_time) > 0 else 0
        prev_time = current_time
        
        cv2.putText(annotated_frame, f"FPS: {int(fps)}", (20, 450), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
        
        # Ekrandaki telefondan gelen bağlantı durumunu da göster
        cv2.putText(annotated_frame, f"Bagli Telefon: {connected_clients}", (20, 420), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 128, 0), 2, cv2.LINE_AA)
        
        # Stream frame update
        with frame_lock:
            global latest_frame
            latest_frame = annotated_frame.copy()
        
        cv2.imshow("Gercek Zamanli Tespit ve Bildirim Senkronizasyonu", annotated_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    import logging
    # Clean up standard flask logging so it doesn't pollute the print statements
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR) 
    main()
