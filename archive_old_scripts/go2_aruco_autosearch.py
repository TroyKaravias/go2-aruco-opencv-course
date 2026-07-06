import cv2
import numpy as np

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

last_seen = {}
cooldown = 2.0

# Autonomous search settings
robot_state = "SEARCHING"
marker_seen_count = 0
MARKER_CONFIRMATION_COUNT = 3
SEARCH_TURN_SPEED = 0.60
SEARCH_COMMAND_INTERVAL = 0.5
last_search_command_time = 0

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


async def search_turn(conn):
    await send_sport_command(
        conn,
        SPORT_CMD["Move"],
        {"x": 0.0, "y": 0.0, "z": SEARCH_TURN_SPEED}
    )


async def handle_marker(conn, marker_id):
    global robot_state

    if robot_state == "DONE":
        return

    robot_state = "FOUND"

    print(f"ArUco marker {marker_id} confirmed.")
    print("Stopping search with StopMove, NOT Damp...")
    await send_sport_command(conn, SPORT_CMD["StopMove"])

    await asyncio.sleep(0.5)

    print("Sitting down / going to rest...")
    await send_sport_command(conn, SPORT_CMD["Sit"])

    robot_state = "DONE"
    print("Autonomous search complete. Robot is now resting.")


# Create an OpenCV window and display a blank image
height, width = 720, 1280  # Adjust the size as needed
img = np.zeros((height, width, 3), dtype=np.uint8)
cv2.imshow('Video', img)
cv2.waitKey(1)  # Ensure the window is created

import asyncio
import logging
import os
import threading
import time
from queue import Queue
from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from unitree_webrtc_connect import RTC_TOPIC, SPORT_CMD
from aiortc import MediaStreamTrack

# Enable logging for debugging
logging.basicConfig(level=logging.FATAL)

ROBOT_IP = os.environ.get("UNITREE_ROBOT_IP", "192.168.8.181")

def main():
    global robot_state
    global marker_seen_count
    global last_search_command_time

    frame_queue = Queue()

    # Choose a connection method (uncomment the correct one)
    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
    # conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, serialNumber="B42D2000XXXXXXXX")
    # conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.Remote, serialNumber="B42D2000XXXXXXXX", username="email@gmail.com", password="pass")
    # conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalAP)

    # Async function to receive video frames and put them in the queue
    async def recv_camera_stream(track: MediaStreamTrack):
        while True:
            frame = await track.recv()
            # Convert the frame to a NumPy array
            img = frame.to_ndarray(format="bgr24")
            frame_queue.put(img)

    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)
        async def setup():
            try:
                # Connect to the device
                await conn.connect()

                # Switch video channel on and start receiving video frames
                conn.video.switchVideoChannel(True)

                # Add callback to handle received video frames
                conn.video.add_track_callback(recv_camera_stream)
            except Exception as e:
                logging.error(f"Error in WebRTC connection: {e}")

        # Run the setup coroutine and then start the event loop
        loop.run_until_complete(setup())
        loop.run_forever()

    # Create a new event loop for the asyncio code
    loop = asyncio.new_event_loop()

    # Start the asyncio event loop in a separate thread
    asyncio_thread = threading.Thread(target=run_asyncio_loop, args=(loop,))
    asyncio_thread.start()

    try:
        while True:
            if not frame_queue.empty():
                img = frame_queue.get()
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                corners, ids, rejected = aruco_detector.detectMarkers(gray)

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

                else:
                    marker_seen_count = 0

                    if robot_state == "SEARCHING":
                        now = time.time()

                        if now - last_search_command_time >= SEARCH_COMMAND_INTERVAL:
                            asyncio.run_coroutine_threadsafe(
                                search_turn(conn),
                                loop
                            )
                            last_search_command_time = now

                cv2.imshow('Video', img)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                # Sleep briefly to prevent high CPU usage
                time.sleep(0.01)
    finally:
        cv2.destroyAllWindows()
        # Stop the asyncio event loop
        loop.call_soon_threadsafe(loop.stop)
        asyncio_thread.join()

if __name__ == "__main__":
    main()
