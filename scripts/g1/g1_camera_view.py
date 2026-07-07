#!/usr/bin/env python3

"""Simple G1 camera viewer for Intel RealSense V4L2 nodes.

Examples:
  python scripts/g1/g1_camera_view.py
  python scripts/g1/g1_camera_view.py --device /dev/video4
  python scripts/g1/g1_camera_view.py --headless --save-first /tmp/frame.jpg
"""

import argparse
import os
import re
import sys
import time

import cv2


def parse_args():
    parser = argparse.ArgumentParser(description="Open G1 camera feed")
    parser.add_argument(
        "--device",
        default=os.environ.get("G1_CAMERA_DEVICE", "/dev/video4"),
        help="V4L2 device path or numeric index (default: /dev/video4)",
    )
    parser.add_argument("--width", type=int, default=640, help="Requested width")
    parser.add_argument("--height", type=int, default=480, help="Requested height")
    parser.add_argument("--fps", type=int, default=30, help="Requested FPS")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without opening a window (useful over SSH)",
    )
    parser.add_argument(
        "--save-first",
        default=None,
        help="Optional path to save the first valid frame",
    )
    return parser.parse_args()


def _open_capture(device):
    # Try path/index exactly as provided first.
    if isinstance(device, str) and device.isdigit():
        cap = cv2.VideoCapture(int(device), cv2.CAP_V4L2)
    else:
        cap = cv2.VideoCapture(device, cv2.CAP_V4L2)

    if cap.isOpened():
        return cap

    cap.release()

    # If '/dev/videoN' was provided, retry using index N.
    if isinstance(device, str):
        match = re.fullmatch(r"/dev/video(\d+)", device)
        if match:
            idx = int(match.group(1))
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            if cap.isOpened():
                return cap
            cap.release()

    return None


def _has_display():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def main():
    args = parse_args()
    use_gui = _has_display() and not args.headless

    cap = _open_capture(args.device)
    if cap is None:
        print(f"[ERROR] Could not open camera device: {args.device}")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    print(f"[INFO] Camera opened: {args.device}")
    print(f"[INFO] Mode: {'GUI' if use_gui else 'HEADLESS'}")
    if use_gui:
        print("[INFO] Press q to quit.")
    else:
        print("[INFO] Press Ctrl+C to quit.")

    frames = 0
    saved_first = False
    last_log = time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.02)
                continue

            frames += 1

            if args.save_first and not saved_first:
                if cv2.imwrite(args.save_first, frame):
                    print(f"[INFO] Saved first frame: {args.save_first}")
                else:
                    print(f"[WARN] Failed to save first frame: {args.save_first}")
                saved_first = True

            if use_gui:
                cv2.imshow("G1 Camera Feed", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            else:
                now = time.time()
                if now - last_log >= 1.0:
                    print(f"[INFO] streaming... frames={frames}")
                    last_log = now

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        if use_gui:
            cv2.destroyAllWindows()
        print("[INFO] Camera viewer stopped.")


if __name__ == "__main__":
    main()
