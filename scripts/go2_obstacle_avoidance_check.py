import asyncio
import json
import logging
import os
import sys

from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from unitree_webrtc_connect.constants import RTC_TOPIC, OBSTACLES_AVOID_API

logging.basicConfig(level=logging.FATAL)

# Use the same IP that has been working for your ArUco project.
ROBOT_IP = os.environ.get("UNITREE_ROBOT_IP", "192.168.12.1")


async def obstacle_switch_set(conn, enable: bool):
    response = await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["OBSTACLES_AVOID"],
        {
            "api_id": OBSTACLES_AVOID_API["SWITCH_SET"],
            "parameter": {"enable": enable},
        },
    )

    code = response.get("data", {}).get("header", {}).get("status", {}).get("code", -1)
    return code, response


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

    return code, enabled, response


async def main():
    print(f"Connecting to Go2 at {ROBOT_IP}...")
    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
    await conn.connect()
    print("Connected.")

    print("\nChecking current obstacle avoidance state...")
    code, enabled, _ = await obstacle_switch_get(conn)
    print(f"Before: enabled={enabled}, code={code}")

    print("\nEnabling built-in obstacle avoidance...")
    code, _ = await obstacle_switch_set(conn, True)
    print(f"Enable command returned code={code}")

    await asyncio.sleep(1)

    print("\nChecking obstacle avoidance state again...")
    code, enabled, _ = await obstacle_switch_get(conn)
    print(f"After: enabled={enabled}, code={code}")

    if enabled is True:
        print("\nSUCCESS: Built-in Go2 obstacle avoidance is enabled.")
    elif enabled is False:
        print("\nWARNING: The command worked, but obstacle avoidance is still reporting disabled.")
    else:
        print("\nWARNING: Could not clearly read obstacle avoidance state.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(0)
