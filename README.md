# unitree-robotics-aruco-opencv

Beginner-friendly course project for controlling a Unitree Go2 with ArUco markers using OpenCV and Python.

Welcome to this course on using Unitree robots with ArUco markers to trigger robot behaviors. My name is Troy Karavias, and I am a student at Stony Brook University working with RoboStore, the official Unitree Robotics partner in the United States. This repository is taught as part of a course on RoboUniversity: https://robouniversity.com.

The repository includes:
- A simple live marker scanner that triggers Go2 actions.
- An autonomous patrol script with marker confirmation, cooldowns, and built-in Go2 obstacle avoidance support.
- A marker generator and course module notes.
- A vendored copy of unitree_webrtc_connect used by the scripts.

## What This Project Does

The camera stream from the Go2 is processed with OpenCV ArUco detection. When known marker IDs are seen, the robot runs mapped actions.

Implemented marker actions (current scripts):

| Marker ID | Action |
| --- | --- |
| 0 | Stop |
| 1 | Stand up |
| 2 | Sit |
| 3 | Short forward move |
| 4 | Short turn/search move |
| 5 | Stretch |
| 6 | Shake hands |
| 7 | Greet |
| 8 | Dance 1 |

## Repository Layout

- `scripts/generate_markers.py`: creates marker images (IDs 0-8) in `aruco_markers/`.
- `scripts/go2_aruco_scan.py`: live camera marker scan + action trigger with cooldown.
- `scripts/go2_aruco_autonomous.py`: autonomous patrol + marker confirmation + obstacle avoidance enable.
- `scripts/go2_obstacle_avoidance_check.py`: utility script to check/enable obstacle avoidance API state.
- `aruco_markers/`: generated marker PNG files.
- `course_docs/`: step-by-step course modules and notes.
- `archive_old_scripts/`: earlier backup/experimental scripts.
- `unitree_webrtc_connect/`: bundled WebRTC SDK source used for robot communication.

## Requirements

- Linux machine (project developed on Ubuntu).
- Python 3.8+.
- Unitree Go2 reachable on local network.
- OpenCV ArUco module (`cv2.aruco`), NumPy, aiortc, and dependencies from `unitree_webrtc_connect`.

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install the local `unitree_webrtc_connect` package and project runtime deps:

```bash
pip install -U pip
pip install -e ./unitree_webrtc_connect
pip install opencv-contrib-python numpy
```

Notes:
- `opencv-contrib-python` is recommended because ArUco is in OpenCV contrib.
- If your environment already has a working OpenCV build with `cv2.aruco`, keep it.

3. Set robot IP once for all scripts:

```bash
export UNITREE_ROBOT_IP=192.168.8.181
```

Use your real robot IP. Setting this env var avoids default-IP differences across scripts.

## Usage

### 1) Generate ArUco markers

```bash
python scripts/generate_markers.py
```

This writes marker images to `aruco_markers/`.

### 1b) Generate a single print-ready 5.5 x 5.5 inch marker

```bash
python scripts/generate_printable_marker.py --id 5 --size-in 5.5 --dpi 300
```

This writes files to `aruco_markers/printables/`:
- PNG at the requested physical size and DPI.
- Matching HTML print sheet with page size locked to 5.5 in x 5.5 in.
- Letter-size HTML print sheet (8.5 x 11) with marker centered at 5.5 in x 5.5 in.

For printing, open the generated HTML file and print with **Scale = 100%** (Actual Size).

### 2) Run basic marker scanner

```bash
python scripts/go2_aruco_scan.py
```

- Opens an OpenCV video window.
- Detects ArUco IDs in view and executes mapped robot actions.
- Press `q` to quit.

### 3) Run autonomous patrol mode

```bash
python scripts/go2_aruco_autonomous.py
```

Behavior implemented now:
- Enables built-in Go2 obstacle avoidance via data channel API.
- Patrol state machine cycles through forward, scan pause, and alternating turn.
- Requires marker confirmation before action.
- Applies per-marker cooldown to avoid repeated triggers.

Press `q` in the camera window to stop.

### 4) Check obstacle avoidance API status only

```bash
python scripts/go2_obstacle_avoidance_check.py
```

## Networking and Connection Notes

- Scripts use local STA WebRTC connection mode (`WebRTCConnectionMethod.LocalSTA`).
- Ensure your laptop and robot are on the same network.
- If your firmware requires AES key based auth, follow the instructions in `unitree_webrtc_connect/README.md` for `unitree-fetch-aes-key`.

## Safety

- Start in an open area with clear perimeter.
- Keep robot speed conservative during testing.
- Be ready to stop motion immediately.
- Validate marker-action mappings before running autonomous mode.

## Course Content

The lesson sequence is in `course_docs/` (modules `00` through `16`) and covers:
- ArUco fundamentals and dictionaries.
- Marker generation and OpenCV detection.
- Go2 command mapping from marker IDs.
- Cooldowns/confirmation logic.
- Scanning while moving and patrol behavior.
- Built-in obstacle avoidance and recovery strategies.

## License

This repository includes a top-level `LICENSE` and also vendors `unitree_webrtc_connect`, which has its own license file in `unitree_webrtc_connect/LICENSE`.
