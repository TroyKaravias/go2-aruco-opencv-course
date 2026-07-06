import asyncio
import contextlib
import logging
import os
import threading
import time
from collections import deque
from queue import Empty, Queue

import cv2
import numpy as np
from flask import Flask, Response, render_template_string
from flask_socketio import SocketIO

from unitree_webrtc_connect import RTC_TOPIC, SPORT_CMD
from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod


logging.basicConfig(level=logging.FATAL)

ROBOT_IP = os.environ.get("UNITREE_ROBOT_IP", "192.168.8.181")
DASHBOARD_HOST = os.environ.get("GO2_DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.environ.get("GO2_DASHBOARD_PORT", "5000"))
JPEG_QUALITY = int(os.environ.get("GO2_DASHBOARD_JPEG_QUALITY", "60"))
FRAME_SCALE = float(os.environ.get("GO2_DASHBOARD_FRAME_SCALE", "0.65"))
DETECT_EVERY_N_FRAMES = max(1, int(os.environ.get("GO2_DASHBOARD_DETECT_EVERY", "2")))

COMMAND_COOLDOWN_SECONDS = 2.0


app = Flask(__name__)
app.config["SECRET_KEY"] = "go2-aruco-dashboard"
socketio = SocketIO(app, cors_allowed_origins="*")


aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

frame_queue = Queue(maxsize=1)
latest_jpeg = None
jpeg_lock = threading.Lock()

running = True
last_seen = {}
log_buffer = deque(maxlen=250)
patrol_enabled = False
patrol_lock = threading.Lock()


HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Go2 ArUco Dashboard</title>
  <style>
    :root {
      --bg: #0d1117;
      --panel: #161b22;
      --text: #dbe6f3;
      --muted: #92a5bf;
      --accent: #2ea043;
      --term-bg: #0a0f14;
      --border: #2d333b;
    }
    body {
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--text);
      background: radial-gradient(circle at 20% 10%, #1c2530, var(--bg) 40%);
    }
    .wrap {
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 16px;
      padding: 16px;
      min-height: 100vh;
      box-sizing: border-box;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .panel h2 {
      margin: 0;
      padding: 12px 14px;
      font-size: 16px;
      border-bottom: 1px solid var(--border);
      color: var(--muted);
    }
    .controls {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      border-bottom: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.02);
    }
    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: #f2cc60;
      box-shadow: 0 0 10px rgba(242, 204, 96, 0.6);
    }
    .status-dot.active {
      background: #4ad66d;
      box-shadow: 0 0 10px rgba(74, 214, 109, 0.6);
    }
    .status-label {
      color: var(--muted);
      font-size: 13px;
      min-width: 130px;
    }
    .btn {
      border: 1px solid var(--border);
      background: #1f6feb;
      color: #fff;
      border-radius: 8px;
      padding: 8px 12px;
      cursor: pointer;
      font-weight: 600;
    }
    .btn.stop {
      background: #da3633;
    }
    .btn:disabled {
      opacity: 0.5;
      cursor: default;
    }
    .feed {
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #000;
      min-height: 420px;
    }
    .terminal {
      background: var(--term-bg);
      font-family: "JetBrains Mono", "Fira Code", monospace;
      font-size: 13px;
      line-height: 1.4;
      padding: 12px;
      overflow: auto;
      height: 100%;
      min-height: 420px;
      white-space: pre-wrap;
    }
    .line {
      margin: 0 0 3px;
    }
    .ok {
      color: #4ad66d;
    }
    .warn {
      color: #f2cc60;
    }
    .err {
      color: #ff6b6b;
    }
    .muted {
      color: var(--muted);
    }
    @media (max-width: 980px) {
      .wrap {
        grid-template-columns: 1fr;
      }
      .feed, .terminal {
        min-height: 300px;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="panel">
      <h2>Go2 Camera Feed</h2>
      <img class="feed" src="/video_feed" alt="Go2 video feed" />
    </section>
    <section class="panel">
      <h2>Live Command Terminal</h2>
      <div class="controls">
        <span id="statusDot" class="status-dot"></span>
        <span id="statusLabel" class="status-label">Standby</span>
        <button id="startBtn" class="btn">Start Patrol</button>
        <button id="stopBtn" class="btn stop" disabled>Stop Patrol</button>
      </div>
      <div id="terminal" class="terminal"></div>
    </section>
  </div>

  <script src="/socket.io/socket.io.js"></script>
  <script>
    const terminal = document.getElementById("terminal");
    const startBtn = document.getElementById("startBtn");
    const stopBtn = document.getElementById("stopBtn");
    const statusLabel = document.getElementById("statusLabel");
    const statusDot = document.getElementById("statusDot");
    const socket = io({ transports: ["websocket", "polling"] });

    function appendLine(text, cssClass = "") {
      const el = document.createElement("div");
      el.className = "line " + cssClass;
      el.textContent = text;
      terminal.appendChild(el);
      terminal.scrollTop = terminal.scrollHeight;
    }

    function setPatrolStatus(enabled) {
      if (enabled) {
        statusLabel.textContent = "Patrol Active";
        statusDot.classList.add("active");
        startBtn.disabled = true;
        stopBtn.disabled = false;
      } else {
        statusLabel.textContent = "Standby";
        statusDot.classList.remove("active");
        startBtn.disabled = false;
        stopBtn.disabled = true;
      }
    }

    startBtn.addEventListener("click", () => {
      socket.emit("set_patrol", { enabled: true });
    });

    stopBtn.addEventListener("click", () => {
      socket.emit("set_patrol", { enabled: false });
    });

    socket.on("connect", () => {
      appendLine("[ui] Socket connected", "muted");
    });

    socket.on("disconnect", () => {
      appendLine("[ui] Socket disconnected", "err");
    });

    socket.on("initial_logs", (payload) => {
      terminal.innerHTML = "";
      for (const line of payload.lines || []) {
        appendLine(line, "muted");
      }
    });

    socket.on("log", (payload) => {
      appendLine(payload.line || "", payload.level || "");
    });

    socket.on("patrol_state", (payload) => {
      setPatrolStatus(Boolean(payload.enabled));
    });

    setPatrolStatus(false);
  </script>
</body>
</html>
"""


def log_event(message, level="muted"):
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    log_buffer.append(line)
    socketio.emit("log", {"line": line, "level": level})


def set_patrol_enabled(enabled):
    global patrol_enabled
    with patrol_lock:
        patrol_enabled = enabled


def is_patrol_enabled():
    with patrol_lock:
        return patrol_enabled


async def send_sport_command(conn, api_id, parameter=None):
    if parameter is None:
        payload = {"api_id": api_id}
    else:
        payload = {"api_id": api_id, "parameter": parameter}

    return await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        payload,
    )


async def handle_marker(conn, marker_id):
    if marker_id == 0:
        log_event("Marker 0 detected -> StopMove", "ok")
        await send_sport_command(conn, SPORT_CMD["StopMove"])
    elif marker_id == 1:
        log_event("Marker 1 detected -> StandUp", "ok")
        await send_sport_command(conn, SPORT_CMD["StandUp"])
    elif marker_id == 2:
        log_event("Marker 2 detected -> Sit", "ok")
        await send_sport_command(conn, SPORT_CMD["Sit"])
    elif marker_id == 3:
        log_event("Marker 3 detected -> Move forward 1s", "ok")
        await send_sport_command(conn, SPORT_CMD["Move"], {"x": 0.20, "y": 0.0, "z": 0.0})
        await asyncio.sleep(1.0)
        await send_sport_command(conn, SPORT_CMD["StopMove"])
    elif marker_id == 4:
        log_event("Marker 4 detected -> Turn left 1s", "ok")
        await send_sport_command(conn, SPORT_CMD["Move"], {"x": 0.0, "y": 0.0, "z": 0.30})
        await asyncio.sleep(1.0)
        await send_sport_command(conn, SPORT_CMD["StopMove"])
    else:
        log_event(f"Marker {marker_id} detected -> no action assigned", "warn")


def update_latest_frame(img):
    global latest_jpeg
    ok, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        return
    with jpeg_lock:
        latest_jpeg = encoded.tobytes()


async def recv_camera_stream(track):
  while running:
    frame = await track.recv()
    img = frame.to_ndarray(format="bgr24")

    if FRAME_SCALE != 1.0:
      img = cv2.resize(img, None, fx=FRAME_SCALE, fy=FRAME_SCALE, interpolation=cv2.INTER_AREA)

    if frame_queue.full():
      try:
        frame_queue.get_nowait()
      except Empty:
        pass

    frame_queue.put(img)


async def process_frames(conn):
    log_event("Video callback active. Processing frames...", "muted")
    command_queue = asyncio.Queue(maxsize=32)
    worker_task = asyncio.create_task(command_worker(conn, command_queue))
    frame_index = 0
    last_detected = []
    last_corners = []

    try:
        while running:
            try:
                img = frame_queue.get_nowait()
            except Empty:
                await asyncio.sleep(0.01)
                continue

            frame_index += 1

            if frame_index % DETECT_EVERY_N_FRAMES == 0:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                corners, ids, _ = aruco_detector.detectMarkers(gray)
                if ids is not None:
                    last_detected = ids.flatten().tolist()
                    last_corners = corners
                else:
                    last_detected = []
                    last_corners = []

            if last_detected:
                ids_arr = np.array(last_detected, dtype=np.int32).reshape(-1, 1)
                # Draw previously detected markers to keep overlays visible between detection passes.
                cv2.aruco.drawDetectedMarkers(img, last_corners, ids_arr)
                now = time.time()

                for marker_id in last_detected:
                    marker_id = int(marker_id)
                    previous = last_seen.get(marker_id, 0)

                    if now - previous > COMMAND_COOLDOWN_SECONDS:
                        if is_patrol_enabled():
                            try:
                                command_queue.put_nowait(marker_id)
                            except asyncio.QueueFull:
                                log_event("Command queue full; dropping marker command", "warn")
                        else:
                            log_event(
                                f"Marker {marker_id} detected while in standby (no command sent)",
                                "warn",
                            )
                        last_seen[marker_id] = now

            cv2.putText(
                img,
                f"Go2 ArUco Dashboard | Q={JPEG_QUALITY} | scale={FRAME_SCALE:.2f} | detect/{DETECT_EVERY_N_FRAMES}",
                (20, max(40, img.shape[0] - 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

            update_latest_frame(img)
    finally:
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task


async def command_worker(conn, command_queue):
    log_event("Command worker active", "muted")
    while running:
        marker_id = await command_queue.get()
        try:
            if not is_patrol_enabled():
                log_event(f"Ignoring marker {marker_id}; patrol is now standby", "warn")
                continue
            await handle_marker(conn, marker_id)
        except Exception as exc:
            log_event(f"Command failed for marker {marker_id}: {exc}", "err")


async def robot_loop():
    log_event(f"Connecting to Go2 at {ROBOT_IP}...", "muted")
    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
    await conn.connect()
    log_event("Connected to Go2", "ok")
    log_event("Robot is in standby. Click Start Patrol in the dashboard.", "warn")

    conn.video.switchVideoChannel(True)
    conn.video.add_track_callback(recv_camera_stream)

    await process_frames(conn)


def robot_thread_main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(robot_loop())
    except Exception as exc:
        log_event(f"Robot loop stopped: {exc}", "err")
    finally:
        loop.stop()
        loop.close()


def mjpeg_generator():
    while True:
        frame = None
        with jpeg_lock:
            if latest_jpeg is not None:
                frame = latest_jpeg

        if frame is None:
            time.sleep(0.05)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/video_feed")
def video_feed():
    return Response(mjpeg_generator(), mimetype="multipart/x-mixed-replace; boundary=frame")


@socketio.on("connect")
def on_connect():
    socketio.emit("initial_logs", {"lines": list(log_buffer)})
    socketio.emit("patrol_state", {"enabled": is_patrol_enabled()})
    log_event("Dashboard client connected", "muted")


@socketio.on("set_patrol")
def on_set_patrol(payload):
    enabled = bool((payload or {}).get("enabled"))
    set_patrol_enabled(enabled)
    state_label = "enabled" if enabled else "standby"
    log_event(f"Patrol mode {state_label} from dashboard", "ok" if enabled else "warn")
    socketio.emit("patrol_state", {"enabled": enabled})


def main():
    thread = threading.Thread(target=robot_thread_main, daemon=True)
    thread.start()

    log_event(f"Dashboard server starting on http://{DASHBOARD_HOST}:{DASHBOARD_PORT}", "muted")
    socketio.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    main()
