import asyncio
import logging
import os
import threading
import time
from queue import Queue

import cv2
import numpy as np
from aiortc import MediaStreamTrack
from unitree_webrtc_connect.webrtc_driver import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
)

logging.basicConfig(level=logging.INFO)

ROBOT_IP = os.environ.get("UNITREE_ROBOT_IP", "192.168.12.1")


# -----------------------------
# Marker action functions
# -----------------------------

def marker_0_action():
    print("Marker 0 scanned: STOP function placeholder")


def marker_1_action():
    print("Marker 1 scanned: STAND function placeholder")


def marker_2_action():
    print("Marker 2 scanned: SIT function placeholder")


def marker_3_action():
    print("Marker 3 scanned: WALK FORWARD function placeholder")


def marker_4_action():
    print("Marker 4 scanned: TURN LEFT function placeholder")


def unknown_marker_action(marker_id):
    print(f"Marker {marker_id} scanned: no function assigned yet")


def run_marker_action(marker_id):
    """
    This is where marker IDs get mapped to robot behaviors.
    For now, these are print statements.
    Later, we can replace them with real Go2 movement commands.
    """
    if marker_id == 0:
        marker_0_action()
    elif marker_id == 1:
        marker_1_action()
    elif marker_id == 2:
        marker_2_action()
    elif marker_id == 3:
        marker_3_action()
    elif marker_id == 4:
        marker_4_action()
    else:
        unknown_marker_action(marker_id)


# -----------------------------
# ArUco detector setup
# -----------------------------

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)


def detect_aruco_markers(frame):
    """
    Detect ArUco markers in one camera frame.
    Returns a list of marker IDs.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = aruco_detector.detectMarkers(gray)

    detected_ids = []

    if ids is not None:
        ids = ids.flatten()
        detected_ids = [int(marker_id) for marker_id in ids]

        # Draw marker outlines and IDs on the frame
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)

        for marker_id, marker_corners in zip(ids, corners):
            c = marker_corners[0]
            center_x = int(c[:, 0].mean())
            center_y = int(c[:, 1].mean())

            cv2.putText(
                frame,
                f"ID: {int(marker_id)}",
                (center_x - 30, center_y - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )

    return detected_ids, frame


# -----------------------------
# Main Go2 camera stream
# -----------------------------

def main():
    frame_queue = Queue(maxsize=3)

    # You are connected to the Go2 hotspot/AP at 192.168.12.1.
    # If this fails, we can switch this to WebRTCConnectionMethod.LocalAP.
    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)

    last_trigger_time = {}
    cooldown_seconds = 2.0

    async def recv_camera_stream(track: MediaStreamTrack):
        while True:
            frame = await track.recv()
            img = frame.to_ndarray(format="bgr24")

            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except Exception:
                    pass

            frame_queue.put(img)

    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)

        async def setup():
            await conn.connect()
            conn.video.switchVideoChannel(True)
            conn.video.add_track_callback(recv_camera_stream)

        loop.run_until_complete(setup())
        loop.run_forever()

    loop = asyncio.new_event_loop()
    asyncio_thread = threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True)
    asyncio_thread.start()

    print("Go2 ArUco detector running.")
    print("Hold an ArUco marker in front of the Go2 camera.")
    print("Press q in the video window to quit.")

    try:
        while True:
            if not frame_queue.empty():
                frame = frame_queue.get()

                detected_ids, annotated_frame = detect_aruco_markers(frame)

                now = time.time()

                for marker_id in detected_ids:
                    last_time = last_trigger_time.get(marker_id, 0)

                    if now - last_time >= cooldown_seconds:
                        run_marker_action(marker_id)
                        last_trigger_time[marker_id] = now

                cv2.imshow("Go2 ArUco Detector", annotated_frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            else:
                time.sleep(0.01)

    finally:
        cv2.destroyAllWindows()
        loop.call_soon_threadsafe(loop.stop)
        asyncio_thread.join(timeout=2)


if __name__ == "__main__":
    main()
