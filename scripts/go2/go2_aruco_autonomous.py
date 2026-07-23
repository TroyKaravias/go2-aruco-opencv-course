import asyncio
import json
import logging
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from queue import Queue

import cv2
import numpy as np

# ── MJPEG stream (headless mode) ──────────────────────────────────────────────
_mjpeg_frame = None
_mjpeg_lock = threading.Lock()
STREAM_PORT = int(os.environ.get("STREAM_PORT", "8080"))
_stop_requested = threading.Event()
_start_requested = threading.Event()

_HTML_PAGE = b"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Go2 Patrol</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #000; display: flex; flex-direction: column; height: 100vh; font-family: sans-serif; }
    #feed { flex: 1; object-fit: contain; width: 100%; }
    #bar {
      display: flex; align-items: center; gap: 12px;
      padding: 8px 14px; background: #111; border-top: 1px solid #333;
    }
    button {
      border: none; border-radius: 6px; padding: 8px 20px;
      font-size: 15px; font-weight: bold; cursor: pointer; color: #fff;
    }
    #startBtn { background: #2ea043; }
    #stopBtn  { background: #da3633; }
    button:disabled { opacity: 0.4; cursor: default; }
    #status { color: #aaa; font-family: monospace; font-size: 13px; }
  </style>
</head>
<body>
  <img id="feed" src="/stream">
  <div id="bar">
    <button id="startBtn" onclick="startPatrol()">Start Patrol</button>
    <button id="stopBtn"  onclick="stopPatrol()" disabled>Stop Patrol</button>
    <span id="status">Standby &#8212; press Start to begin</span>
  </div>
  <script>
    function startPatrol() {
      document.getElementById('startBtn').disabled = true;
      document.getElementById('stopBtn').disabled = false;
      document.getElementById('status').textContent = 'Patrol running...';
      fetch('/start');
    }
    function stopPatrol() {
      document.getElementById('stopBtn').disabled = true;
      document.getElementById('startBtn').disabled = true;
      document.getElementById('status').textContent = 'Stopping...';
      fetch('/stop').then(() => {
        document.getElementById('status').textContent = 'Stopped.';
      }).catch(() => {
        document.getElementById('status').textContent = 'Stop sent.';
      });
    }
  </script>
</body>
</html>"""


def _set_mjpeg_frame(img, quality=60):
    global _mjpeg_frame
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        with _mjpeg_lock:
            _mjpeg_frame = buf.tobytes()


class _MJPEGHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress request logs

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(_HTML_PAGE)
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    with _mjpeg_lock:
                        frame = _mjpeg_frame
                    if frame:
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                            + frame + b"\r\n"
                        )
                    time.sleep(0.05)
            except Exception:
                pass
        elif self.path == "/start":
            _stop_requested.clear()
            _start_requested.set()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"started")
        elif self.path == "/stop":
            _stop_requested.set()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"stopping")
        else:
            self.send_response(404)
            self.end_headers()


def _start_mjpeg_server(port):
    class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
    server = _ThreadedHTTPServer(("0.0.0.0", port), _MJPEGHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server
# ──────────────────────────────────────────────────────────────────────────────

from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection
from unitree_webrtc_connect.constants import RTC_TOPIC, OBSTACLES_AVOID_API, SPORT_CMD

logging.basicConfig(level=logging.FATAL)

# ============================================================
# Course Module:
# Autonomous ArUco Search with Built-In Go2 Obstacle Avoidance
# ============================================================

# When running ON the robot via SSH, leave UNITREE_ROBOT_IP unset and
# RUN_ON_ROBOT=1 will be detected automatically (no DISPLAY available).
# When running from a laptop on the same network, set UNITREE_ROBOT_IP.
ROBOT_IP = os.environ.get("UNITREE_ROBOT_IP", "192.168.12.1")

# Headless mode: automatically true when there is no DISPLAY (e.g. SSH on robot).
# Override with HEADLESS=1 or HEADLESS=0.
_headless_env = os.environ.get("HEADLESS", "")
if _headless_env == "1":
    HEADLESS = True
elif _headless_env == "0":
    HEADLESS = False
else:
    HEADLESS = not bool(os.environ.get("DISPLAY", ""))

# Connection method: LocalAP when running on the robot (no UNITREE_ROBOT_IP set
# and headless), LocalSTA when connecting from a laptop on the same network.
_run_on_robot = HEADLESS and not os.environ.get("UNITREE_ROBOT_IP", "")
if _run_on_robot:
    from unitree_webrtc_connect.constants import WebRTCConnectionMethod as _WCM
    _CONNECTION_METHOD = _WCM.LocalAP
else:
    from unitree_webrtc_connect.constants import WebRTCConnectionMethod as _WCM
    _CONNECTION_METHOD = _WCM.LocalSTA

# ArUco setup
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

# Marker confirmation
MARKER_CONFIRMATION_COUNT = 2
cooldown = 2.0
last_seen = {}
marker_seen_count = {}

# Autonomous movement settings
# Keep these slow for the first course demo.
SEARCH_TURN_SPEED = 0.28
FORWARD_SPEED = 0.28

# Patrol behavior settings
PATROL_FORWARD_TIME = 3.0
PATROL_SCAN_TIME = 1.0
PATROL_TURN_TIME = 1.8

patrol_state = "FORWARD"
patrol_state_start = time.time()
patrol_turn_direction = 1

# Stronger wall/corner recovery settings.
# The robot watches the camera image while it is commanded forward.
# If the view barely changes while the robot is supposed to be moving,
# the script assumes the robot may be stuck against a wall/corner/obstacle.
FORWARD_BLOCKED_TIME = 1.4
VISUAL_MOTION_THRESHOLD = 5.0

# Do not check for blocked motion immediately after entering FORWARD.
# This prevents false recovery triggers during startup, after turns,
# or while the camera image is still settling.
BLOCK_CHECK_GRACE_TIME = 1.0

# Normal recovery
RECOVERY_STOP_TIME = 0.35
RECOVERY_BACKUP_TIME = 2.0
RECOVERY_TURN_TIME = 3.0
RECOVERY_SCAN_TIME = 0.8

RECOVERY_BACKUP_SPEED = -0.34
RECOVERY_TURN_SPEED = 0.385

# Emergency recovery if the robot gets stuck again soon after recovery.
# Important:
# The second recovery backs up farther, but turns LESS.
# A smaller opposite turn helps avoid swinging back into the same corner.
RECOVERY_REPEAT_WINDOW = 8.0
EMERGENCY_BACKUP_TIME = 2.8
EMERGENCY_TURN_TIME = 2.2
EMERGENCY_BACKUP_SPEED = -0.38
EMERGENCY_TURN_SPEED = 0.455

# Recovery tracking
blocked_since = None
last_gray_frame = None
last_recovery_time = 0.0
recovery_is_emergency = False
recovery_turn_direction = 1

# Wireless controller topic settings.
# For this topic:
# lx = left/right strafe
# ly = forward/back
# rx = turn left/right
PUBLISH_INTERVAL = 0.05


def print_course_header():
    print("\n============================================================")
    print("Go2 Autonomous ArUco Patrol")
    print("Built-in Go2 obstacle avoidance will be enabled first.")
    if HEADLESS:
        print("Running HEADLESS (no display). Press CTRL+C to stop.")
    else:
        print("Press q in the camera window to stop.")
        print("CTRL+C also stops the script.")
    print("============================================================\n")


async def obstacle_switch_set(conn, enable: bool):
    response = await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["OBSTACLES_AVOID"],
        {
            "api_id": OBSTACLES_AVOID_API["SWITCH_SET"],
            "parameter": {"enable": enable},
        },
    )

    code = response.get("data", {}).get("header", {}).get("status", {}).get("code", -1)
    return code


async def obstacle_switch_get(conn):
    response = await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["OBSTACLES_AVOID"],
        {
            "api_id": OBSTACLES_AVOID_API["SWITCH_GET"],
        },
    )

    code = response.get("data", {}).get("header", {}).get("status", {}).get("code", -1)
    data = response.get("data", {}).get("data", "")

    enabled = None
    if code == 0 and data:
        try:
            enabled = json.loads(data).get("enable")
        except Exception:
            enabled = None

    return code, enabled


async def enable_builtin_obstacle_avoidance(conn):
    print("Checking built-in obstacle avoidance...")
    code, enabled = await obstacle_switch_get(conn)
    print(f"Obstacle avoidance before command: enabled={enabled}, code={code}")

    print("Enabling built-in obstacle avoidance...")
    code = await obstacle_switch_set(conn, True)
    print(f"Enable command returned code={code}")

    await asyncio.sleep(0.5)

    code, enabled = await obstacle_switch_get(conn)
    print(f"Obstacle avoidance after command: enabled={enabled}, code={code}")

    if enabled is True:
        print("SUCCESS: Built-in obstacle avoidance is enabled.\n")
    else:
        print("WARNING: Could not confirm obstacle avoidance is enabled.\n")


def publish_wireless_controller(pub_sub, lx=0.0, ly=0.0, rx=0.0, ry=0.0, keys=0):
    """
    Sends joystick-style movement commands.

    This is useful for this course stage because Go2's built-in
    obstacle avoidance can safety-filter wireless controller movement.
    """
    pub_sub.publish_without_callback(
        RTC_TOPIC["WIRELESS_CONTROLLER"],
        {
            "lx": lx,
            "ly": ly,
            "rx": rx,
            "ry": ry,
            "keys": keys,
        },
    )


async def stop_robot(conn):
    # Publish zero wireless-controller values to stop autonomous movement.
    # Do NOT send StopMove — that sport command locks out the physical controller.
    publish_wireless_controller(conn.datachannel.pub_sub, 0.0, 0.0, 0.0)


def get_visual_motion_score(img):
    """
    Returns a simple motion score based on how much the camera image changed
    since the last frame.

    Higher score = camera view is changing.
    Lower score = camera view is barely changing.
    """
    global last_gray_frame

    small = cv2.resize(img, (160, 120))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    if last_gray_frame is None:
        last_gray_frame = gray
        return None

    diff = cv2.absdiff(last_gray_frame, gray)
    score = float(np.mean(diff))

    last_gray_frame = gray
    return score


async def start_recovery(conn, now):
    """
    Starts normal or emergency recovery depending on whether the robot
    got stuck again shortly after a previous recovery.

    Normal recovery:
    - backs up
    - turns a little more than 90 degrees

    Emergency recovery:
    - backs up farther
    - turns less
    - turns in the opposite direction from the previous recovery
    """
    global patrol_state, patrol_state_start
    global blocked_since, last_recovery_time, recovery_is_emergency
    global recovery_turn_direction

    if now - last_recovery_time <= RECOVERY_REPEAT_WINDOW:
        recovery_is_emergency = True
        recovery_turn_direction *= -1
        print("Blocked again soon after recovery. Using EMERGENCY recovery.")
        print("Emergency recovery will back up farther and use a smaller opposite turn.")
    else:
        recovery_is_emergency = False
        recovery_turn_direction = patrol_turn_direction
        print("Forward movement appears blocked. Starting normal recovery.")

    last_recovery_time = now
    blocked_since = None
    patrol_state = "RECOVERY_STOP"
    patrol_state_start = now

    await stop_robot(conn)


async def search_motion(conn, current_frame=None):
    """
    Autonomous patrol behavior with stronger wall/corner recovery.

    Normal patrol:
    1. walk forward,
    2. stop and scan,
    3. turn left/right,
    4. walk forward again.

    Stronger recovery:
    If the robot is commanded forward but the camera image barely changes,
    the robot stops, backs up, turns farther, scans briefly, then resumes.
    """
    global patrol_state, patrol_state_start, patrol_turn_direction
    global blocked_since

    now = time.time()
    elapsed = now - patrol_state_start

    if patrol_state == "FORWARD":
        motion_score = None

        if current_frame is not None:
            motion_score = get_visual_motion_score(current_frame)

            if motion_score is not None:
                cv2.putText(
                    current_frame,
                    f"motion {motion_score:.1f}",
                    (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

        # Only check for being stuck after the robot has been moving
        # forward long enough for the camera view to actually change.
        can_check_blocked = elapsed >= BLOCK_CHECK_GRACE_TIME

        if (
            can_check_blocked
            and motion_score is not None
            and motion_score < VISUAL_MOTION_THRESHOLD
        ):
            if blocked_since is None:
                blocked_since = now
                print(f"Low camera motion detected: {motion_score:.1f}")
            elif now - blocked_since >= FORWARD_BLOCKED_TIME:
                print(
                    f"Robot may be stuck. Motion score={motion_score:.1f}, "
                    f"blocked for {now - blocked_since:.1f}s"
                )
                await start_recovery(conn, now)
                return
        else:
            blocked_since = None

        publish_wireless_controller(
            conn.datachannel.pub_sub,
            lx=0.0,
            ly=FORWARD_SPEED,
            rx=0.0,
        )

        if elapsed >= PATROL_FORWARD_TIME:
            patrol_state = "SCAN"
            patrol_state_start = now
            blocked_since = None
            print("Patrol state: SCAN")
            await stop_robot(conn)

    elif patrol_state == "SCAN":
        await stop_robot(conn)

        if elapsed >= PATROL_SCAN_TIME:
            patrol_state = "TURN"
            patrol_state_start = now
            patrol_turn_direction *= -1
            print(f"Patrol state: TURN {'LEFT' if patrol_turn_direction > 0 else 'RIGHT'}")

    elif patrol_state == "TURN":
        publish_wireless_controller(
            conn.datachannel.pub_sub,
            lx=0.0,
            ly=0.0,
            rx=SEARCH_TURN_SPEED * patrol_turn_direction,
        )

        if elapsed >= PATROL_TURN_TIME:
            patrol_state = "FORWARD"
            patrol_state_start = now
            blocked_since = None
            print("Patrol state: FORWARD")
            await stop_robot(conn)

    elif patrol_state == "RECOVERY_STOP":
        await stop_robot(conn)

        if elapsed >= RECOVERY_STOP_TIME:
            patrol_state = "RECOVERY_BACKUP"
            patrol_state_start = now

            if recovery_is_emergency:
                print("Emergency recovery: backing up farther.")
            else:
                print("Recovery: backing up.")

    elif patrol_state == "RECOVERY_BACKUP":
        if recovery_is_emergency:
            backup_time = EMERGENCY_BACKUP_TIME
            backup_speed = EMERGENCY_BACKUP_SPEED
        else:
            backup_time = RECOVERY_BACKUP_TIME
            backup_speed = RECOVERY_BACKUP_SPEED

        publish_wireless_controller(
            conn.datachannel.pub_sub,
            lx=0.0,
            ly=backup_speed,
            rx=0.0,
        )

        if elapsed >= backup_time:
            await stop_robot(conn)
            patrol_state = "RECOVERY_TURN"
            patrol_state_start = now

            if recovery_is_emergency:
                print("Emergency recovery: turning farther.")
            else:
                print("Recovery: turning away from obstacle.")

    elif patrol_state == "RECOVERY_TURN":
        if recovery_is_emergency:
            turn_time = EMERGENCY_TURN_TIME
            turn_speed = EMERGENCY_TURN_SPEED
        else:
            turn_time = RECOVERY_TURN_TIME
            turn_speed = RECOVERY_TURN_SPEED

        publish_wireless_controller(
            conn.datachannel.pub_sub,
            lx=0.0,
            ly=0.0,
            rx=turn_speed * recovery_turn_direction,
        )

        if elapsed >= turn_time:
            await stop_robot(conn)
            patrol_state = "RECOVERY_SCAN"
            patrol_state_start = now
            print("Recovery turn complete. Scanning briefly before moving forward.")

    elif patrol_state == "RECOVERY_SCAN":
        publish_wireless_controller(
            conn.datachannel.pub_sub,
            lx=0.0,
            ly=0.0,
            rx=SEARCH_TURN_SPEED,
        )

        if elapsed >= RECOVERY_SCAN_TIME:
            await stop_robot(conn)
            patrol_state = "FORWARD"
            patrol_state_start = now
            blocked_since = None
            print("Recovery complete. Returning to patrol.")

    else:
        patrol_state = "FORWARD"
        patrol_state_start = now
        blocked_since = None
        await stop_robot(conn)


async def move_forward_short(conn, seconds=0.6):
    """
    Optional cautious forward burst.
    Not used continuously yet. We keep it available for the next step.
    """
    start = time.time()
    while time.time() - start < seconds:
        publish_wireless_controller(
            conn.datachannel.pub_sub,
            lx=0.0,
            ly=FORWARD_SPEED,
            rx=0.0,
        )
        await asyncio.sleep(PUBLISH_INTERVAL)

    await stop_robot(conn)


async def send_sport_command(conn, api_id, parameter=None):
    if parameter is None:
        payload = {"api_id": api_id}
    else:
        payload = {
            "api_id": api_id,
            "parameter": parameter,
        }

    return await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        payload,
    )


async def handle_marker(conn, marker_id):
    """
    Marker actions for the course demo.

    Marker 0: Stop
    Marker 1: Stand up
    Marker 2: Sit
    Marker 3: Move forward briefly, then stop
    Marker 4: Turn/search behavior
    Marker 5: Stretch
    Marker 6: Shake hands (mapped to Content gesture)
    Marker 7: Greet (Hello gesture)
    Marker 8: Dance 1
    """

    now = time.time()

    if marker_id in last_seen and now - last_seen[marker_id] < cooldown:
        return

    last_seen[marker_id] = now

    print(f"\nConfirmed ArUco marker ID: {marker_id}")
    print("Stopping before marker action...")
    await stop_robot(conn)
    await asyncio.sleep(0.3)

    if marker_id == 0:
        print("Marker 0 action: StopMove")
        await stop_robot(conn)

    elif marker_id == 1:
        print("Marker 1 action: StandUp")
        await send_sport_command(conn, SPORT_CMD["StandUp"])

    elif marker_id == 2:
        print("Marker 2 action: Sit")
        await send_sport_command(conn, SPORT_CMD["Sit"])

    elif marker_id == 3:
        print("Marker 3 action: cautious forward burst, then stop")
        await move_forward_short(conn, seconds=0.7)

    elif marker_id == 4:
        print("Marker 4 action: turn/search")
        start = time.time()
        while time.time() - start < 1.0:
            publish_wireless_controller(
                conn.datachannel.pub_sub,
                lx=0.0,
                ly=0.0,
                rx=SEARCH_TURN_SPEED,
            )
            await asyncio.sleep(PUBLISH_INTERVAL)
        await stop_robot(conn)

    elif marker_id == 5:
        print("Marker 5 action: Stretch")
        await send_sport_command(conn, SPORT_CMD["Stretch"])

    elif marker_id == 6:
        print("Marker 6 action: Shake hands (Content gesture)")
        await send_sport_command(conn, SPORT_CMD["Content"])

    elif marker_id == 7:
        print("Marker 7 action: Greet (Hello)")
        await send_sport_command(conn, SPORT_CMD["Hello"])

    elif marker_id == 8:
        print("Marker 8 action: Dance 1")
        await send_sport_command(conn, SPORT_CMD["Dance1"])

    else:
        print(f"No action assigned for marker {marker_id}")

    await asyncio.sleep(0.5)
    print("Returning to autonomous search...\n")


async def video_loop(conn):
    """
    Reads frames from the Go2 video callback, detects ArUco markers,
    and controls autonomous search behavior.

    This uses the correct unitree_webrtc_connect camera style:
    conn.video.switchVideoChannel(True)
    conn.video.add_track_callback(callback)
    """

    print("Starting Go2 camera video channel...")

    frame_queue = Queue(maxsize=2)

    async def recv_camera_stream(track):
        while True:
            frame = await track.recv()
            img = frame.to_ndarray(format="bgr24")

            # Keep only the newest frame so the robot does not lag behind.
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except Exception:
                    pass

            frame_queue.put(img)

    conn.video.switchVideoChannel(True)
    conn.video.add_track_callback(recv_camera_stream)

    print("Camera callback added. Waiting for frames...\n")

    _prev_patrol_active = False  # track transitions so we can reset state on Start

    try:
        while True:
            if frame_queue.empty():
                await asyncio.sleep(0.01)
                continue

            img = frame_queue.get()

            corners, ids, rejected = aruco_detector.detectMarkers(img)

            marker_detected_this_frame = False

            if ids is not None:
                cv2.aruco.drawDetectedMarkers(img, corners, ids)

                visible_ids = ids.flatten().tolist()
                print(f"Visible ArUco IDs: {visible_ids}")

                # Stop immediately when a marker is visible so the camera
                # has time to confirm and scan it instead of passing by.
                await stop_robot(conn)

                for marker_id in visible_ids:
                    marker_detected_this_frame = True

                    marker_seen_count[marker_id] = marker_seen_count.get(marker_id, 0) + 1

                    cv2.putText(
                        img,
                        f"ID {marker_id} count {marker_seen_count[marker_id]}",
                        (20, 40 + 30 * visible_ids.index(marker_id)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2,
                    )

                    if marker_seen_count[marker_id] >= MARKER_CONFIRMATION_COUNT:
                        marker_seen_count[marker_id] = 0
                        await handle_marker(conn, marker_id)

                # Reset counts for markers no longer visible
                for old_id in list(marker_seen_count.keys()):
                    if old_id not in visible_ids:
                        marker_seen_count[old_id] = 0

            else:
                marker_seen_count.clear()

            # Headless: check start/stop state from browser buttons.
            # Non-headless: patrol runs immediately (use q to quit).
            if HEADLESS:
                patrol_active = _start_requested.is_set() and not _stop_requested.is_set()
            else:
                patrol_active = True

            # Detect transitions before updating _prev_patrol_active.
            _transitioning_to_active = patrol_active and not _prev_patrol_active
            _transitioning_to_standby = not patrol_active and _prev_patrol_active

            # Reset patrol state machine the moment Start is clicked so elapsed
            # time doesn't instantly skip through all the patrol states.
            if _transitioning_to_active:
                global patrol_state, patrol_state_start, blocked_since
                patrol_state = "FORWARD"
                patrol_state_start = time.time()
                blocked_since = None
                print("Patrol started.")
            _prev_patrol_active = patrol_active

            if patrol_active and not marker_detected_this_frame:
                await search_motion(conn, img)
            elif _transitioning_to_standby and not marker_detected_this_frame:
                # Only send stop once on transition to standby, not every frame.
                # Sending StopMove every frame overrides the physical controller.
                await stop_robot(conn)

            if HEADLESS and not _start_requested.is_set():
                status_text = "STANDBY | Open browser and press Start"
            elif HEADLESS and _stop_requested.is_set():
                status_text = "STOPPED"
            else:
                status_text = f"AUTO PATROL | State: {patrol_state}"

            cv2.putText(
                img,
                status_text,
                (20, img.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0) if patrol_active else (0, 165, 255),
                2,
            )

            if HEADLESS:
                _set_mjpeg_frame(img)
            else:
                cv2.imshow("Go2 Autonomous ArUco Patrol", img)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("q pressed. Stopping robot and exiting.")
                    break

            await asyncio.sleep(0.001)

    finally:
        await stop_robot(conn)
        if not HEADLESS:
            cv2.destroyAllWindows()


async def main():
    print_course_header()

    if HEADLESS:
        _start_mjpeg_server(STREAM_PORT)
        print(f"MJPEG stream started on http://192.168.123.170:{STREAM_PORT}\n")

    if _run_on_robot:
        print("Connecting to Go2 via LocalAP (running on robot)...")
        conn = UnitreeWebRTCConnection(_CONNECTION_METHOD)
    else:
        print(f"Connecting to Go2 at {ROBOT_IP}...")
        conn = UnitreeWebRTCConnection(_CONNECTION_METHOD, ip=ROBOT_IP)
    await conn.connect()
    print("Connected.\n")

    await enable_builtin_obstacle_avoidance(conn)

    # Make sure robot is stopped before autonomy starts
    await stop_robot(conn)

    await video_loop(conn)

    await stop_robot(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCTRL+C pressed. Exiting.")
        if not HEADLESS:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        sys.exit(0)
