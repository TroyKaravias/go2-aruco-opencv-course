import cv2
import numpy as np

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

last_seen = {}
cooldown = 2.0

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
    if marker_id == 0:
        print("Marker 0 scanned: sending StopMove, NOT Damp")
        await send_sport_command(conn, SPORT_CMD["StopMove"])

    elif marker_id == 1:
        print("Marker 1 scanned: sending StandUp")
        await send_sport_command(conn, SPORT_CMD["StandUp"])

    elif marker_id == 2:
        print("Marker 2 scanned: sending Sit")
        await send_sport_command(conn, SPORT_CMD["Sit"])

    elif marker_id == 3:
        print("Marker 3 scanned: walking forward slowly for 1 second")
        await send_sport_command(
            conn,
            SPORT_CMD["Move"],
            {"x": 0.20, "y": 0.0, "z": 0.0}
        )
        await asyncio.sleep(1.0)
        await send_sport_command(conn, SPORT_CMD["StopMove"])

    elif marker_id == 4:
        print("Marker 4 scanned: turning left slowly for 1 second")
        await send_sport_command(
            conn,
            SPORT_CMD["Move"],
            {"x": 0.0, "y": 0.0, "z": 0.30}
        )
        await asyncio.sleep(1.0)
        await send_sport_command(conn, SPORT_CMD["StopMove"])

    elif marker_id == 5:
        print("Marker 5 scanned: sending Stretch")
        await send_sport_command(conn, SPORT_CMD["Stretch"])

    elif marker_id == 6:
        print("Marker 6 scanned: sending Shake Hands (Content gesture)")
        await send_sport_command(conn, SPORT_CMD["Content"])

    elif marker_id == 7:
        print("Marker 7 scanned: sending Greet (Hello)")
        await send_sport_command(conn, SPORT_CMD["Hello"])

    elif marker_id == 8:
        print("Marker 8 scanned: sending Dance 1")
        await send_sport_command(conn, SPORT_CMD["Dance1"])

    else:
        print(f"Marker {marker_id} scanned: no action assigned")

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

                    now = time.time()

                    for marker_id in ids:
                        marker_id = int(marker_id)
                        previous = last_seen.get(marker_id, 0)

                        if now - previous > cooldown:
                            asyncio.run_coroutine_threadsafe(
                                handle_marker(conn, marker_id),
                                loop
                            )
                            last_seen[marker_id] = now

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
