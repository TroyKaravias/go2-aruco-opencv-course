import asyncio
import json
import logging
import os
import sys
import time
from queue import Queue

import cv2
import numpy as np

from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from unitree_webrtc_connect.constants import RTC_TOPIC, OBSTACLES_AVOID_API, SPORT_CMD

logging.basicConfig(level=logging.FATAL)

# ============================================================
# Course Module:
# Autonomous ArUco Search with Built-In Go2 Obstacle Avoidance
# ============================================================

# Use the same Go2 IP that has been working for your ArUco project.
ROBOT_IP = os.environ.get("UNITREE_ROBOT_IP", "192.168.12.1")

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
    # Stop wireless-controller movement
    publish_wireless_controller(conn.datachannel.pub_sub, 0.0, 0.0, 0.0)

    # Also send sport StopMove as a second safety stop
    try:
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"],
            {"api_id": SPORT_CMD["StopMove"]},
        )
    except Exception:
        pass


async def search_motion(conn):
    """
    Simple patrol behavior.

    Instead of spinning in one direction forever, the robot cycles through:
    1. walking forward,
    2. stopping to scan,
    3. turning left or right,
    4. walking forward again.

    Built-in Go2 obstacle avoidance remains enabled.
    """
    global patrol_state, patrol_state_start, patrol_turn_direction

    now = time.time()
    elapsed = now - patrol_state_start

    if patrol_state == "FORWARD":
        publish_wireless_controller(
            conn.datachannel.pub_sub,
            lx=0.0,
            ly=FORWARD_SPEED,
            rx=0.0,
        )

        if elapsed >= PATROL_FORWARD_TIME:
            patrol_state = "SCAN"
            patrol_state_start = now
            print("Patrol state: SCAN")
            await stop_robot(conn)

    elif patrol_state == "SCAN":
        # Stop briefly so the camera can get a clean look around.
        await stop_robot(conn)

        if elapsed >= PATROL_SCAN_TIME:
            patrol_state = "TURN"
            patrol_state_start = now

            # Alternate turn direction each time so it patrols more naturally.
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
            print("Patrol state: FORWARD")
            await stop_robot(conn)

    else:
        patrol_state = "FORWARD"
        patrol_state_start = now
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

            if not marker_detected_this_frame:
                await search_motion(conn)

            cv2.putText(
                img,
                "AUTO PATROL | Built-in obstacle avoidance ON | q = quit",
                (20, img.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

            cv2.imshow("Go2 Autonomous ArUco Patrol", img)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("q pressed. Stopping robot and exiting.")
                break

            await asyncio.sleep(0.001)

    finally:
        await stop_robot(conn)
        cv2.destroyAllWindows()


async def main():
    print_course_header()

    print(f"Connecting to Go2 at {ROBOT_IP}...")
    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
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
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        sys.exit(0)
