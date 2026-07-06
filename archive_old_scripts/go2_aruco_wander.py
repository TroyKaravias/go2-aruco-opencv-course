import cv2
import numpy as np

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

last_seen = {}
cooldown = 2.0

# Autonomous wander settings
robot_state = "SEARCHING"
patrol_state = "TURNING"
marker_seen_count = 0
MARKER_CONFIRMATION_COUNT = 3

SEARCH_TURN_SPEED = 0.60
FORWARD_SPEED = 0.15

TURN_SCAN_SECONDS = 3.0
FORWARD_SECONDS = 1.0
PAUSE_SECONDS = 0.5
COMMAND_INTERVAL = 0.4

last_command_time = 0
patrol_state_start_time = 0
turn_direction = 1


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


async def stop_move(conn):
    await send_sport_command(conn, SPORT_CMD["StopMove"])


async def turn_search(conn):
    await send_sport_command(
        conn,
        SPORT_CMD["Move"],
        {"x": 0.0, "y": 0.0, "z": SEARCH_TURN_SPEED * turn_direction}
    )


async def walk_forward(conn):
    await send_sport_command(
        conn,
        SPORT_CMD["Move"],
        {"x": FORWARD_SPEED, "y": 0.0, "z": 0.0}
    )


async def handle_marker(conn, marker_id):
    global robot_state

    if robot_state == "DONE":
        return

    robot_state = "FOUND"

    print(f"ArUco marker {marker_id} confirmed.")
    print("Stopping with StopMove, NOT Damp...")
    await stop_move(conn)

    await asyncio.sleep(0.5)

    print("Sitting down / going to rest...")
    await send_sport_command(conn, SPORT_CMD["Sit"])

    robot_state = "DONE"
    print("Autonomous wandering complete. Robot is now resting.")


# Create an OpenCV window and display a blank image
height, width = 720, 1280
img = np.zeros((height, width, 3), dtype=np.uint8)
cv2.imshow('Video', img)
cv2.waitKey(1)

import asyncio
import logging
import os
import threading
import time
from queue import Queue
from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from unitree_webrtc_connect import RTC_TOPIC, SPORT_CMD
from aiortc import MediaStreamTrack

logging.basicConfig(level=logging.FATAL)

ROBOT_IP = os.environ.get("UNITREE_ROBOT_IP", "192.168.8.181")


def main():
    global robot_state
    global patrol_state
    global marker_seen_count
    global last_command_time
    global patrol_state_start_time
    global turn_direction

    frame_queue = Queue()
    patrol_state_start_time = time.time()

    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)

    async def recv_camera_stream(track: MediaStreamTrack):
        while True:
            frame = await track.recv()
            img = frame.to_ndarray(format="bgr24")
            frame_queue.put(img)

    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)

        async def setup():
            try:
                await conn.connect()
                conn.video.switchVideoChannel(True)
                conn.video.add_track_callback(recv_camera_stream)
            except Exception as e:
                logging.error(f"Error in WebRTC connection: {e}")

        loop.run_until_complete(setup())
        loop.run_forever()

    loop = asyncio.new_event_loop()
    asyncio_thread = threading.Thread(target=run_asyncio_loop, args=(loop,))
    asyncio_thread.start()

    print("Go2 ArUco wander is running.")
    print("Behavior:")
    print("1. Turn and scan")
    print("2. If no marker is found, walk forward slowly")
    print("3. Stop, turn the other way, and scan again")
    print("4. When a marker is seen 3 times, StopMove then Sit")
    print("Press q in the video window to quit.")

    try:
        while True:
            if not frame_queue.empty():
                img = frame_queue.get()
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                corners, ids, rejected = aruco_detector.detectMarkers(gray)

                now = time.time()

                if ids is not None:
                    ids = ids.flatten()
                    cv2.aruco.drawDetectedMarkers(img, corners, ids)

                    if robot_state == "SEARCHING":
                        marker_seen_count += 1
                        marker_id = int(ids[0])

                        print(
                            f"Marker candidate seen: ID {marker_id} "
                            f"({marker_seen_count}/{MARKER_CONFIRMATION_COUNT})"
                        )

                        if marker_seen_count >= MARKER_CONFIRMATION_COUNT:
                            asyncio.run_coroutine_threadsafe(
                                handle_marker(conn, marker_id),
                                loop
                            )

                else:
                    marker_seen_count = 0

                    if robot_state == "SEARCHING":
                        state_elapsed = now - patrol_state_start_time

                        if patrol_state == "TURNING":
                            if now - last_command_time >= COMMAND_INTERVAL:
                                asyncio.run_coroutine_threadsafe(
                                    turn_search(conn),
                                    loop
                                )
                                last_command_time = now

                            if state_elapsed >= TURN_SCAN_SECONDS:
                                asyncio.run_coroutine_threadsafe(
                                    stop_move(conn),
                                    loop
                                )
                                patrol_state = "PAUSE_AFTER_TURN"
                                patrol_state_start_time = now
                                print("No marker found while turning. Preparing to walk forward...")

                        elif patrol_state == "PAUSE_AFTER_TURN":
                            if state_elapsed >= PAUSE_SECONDS:
                                patrol_state = "FORWARD"
                                patrol_state_start_time = now
                                print("Walking forward slowly...")

                        elif patrol_state == "FORWARD":
                            if now - last_command_time >= COMMAND_INTERVAL:
                                asyncio.run_coroutine_threadsafe(
                                    walk_forward(conn),
                                    loop
                                )
                                last_command_time = now

                            if state_elapsed >= FORWARD_SECONDS:
                                asyncio.run_coroutine_threadsafe(
                                    stop_move(conn),
                                    loop
                                )
                                patrol_state = "PAUSE_AFTER_FORWARD"
                                patrol_state_start_time = now
                                print("Forward step complete. Stopping...")

                        elif patrol_state == "PAUSE_AFTER_FORWARD":
                            if state_elapsed >= PAUSE_SECONDS:
                                turn_direction *= -1
                                patrol_state = "TURNING"
                                patrol_state_start_time = now
                                print("Turning again to search...")

                if robot_state == "SEARCHING":
                    cv2.putText(
                        img,
                        f"SEARCHING - {patrol_state}",
                        (40, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 255, 255),
                        3,
                    )

                elif robot_state == "DONE":
                    cv2.putText(
                        img,
                        "DONE - ROBOT RESTING",
                        (40, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 255, 0),
                        3,
                    )

                cv2.imshow('Video', img)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            else:
                time.sleep(0.01)

    finally:
        print("Closing program. Sending StopMove.")
        asyncio.run_coroutine_threadsafe(
            stop_move(conn),
            loop
        )
        time.sleep(0.5)

        cv2.destroyAllWindows()
        loop.call_soon_threadsafe(loop.stop)
        asyncio_thread.join()


if __name__ == "__main__":
    main()
