cd ~/projects/go2_aruco_opencv

cat > COURSE_NOTES.md <<'MD'
# Autonomous Unitree Go2 Control with ArUco Markers and OpenCV

## Course Overview

In this course, students will learn how to use computer vision to control a Unitree Go2 robot dog with printed ArUco markers.

The main idea is simple:

> ArUco markers act like visual command signs that the robot can read through its camera.

Instead of only controlling the Go2 with a joystick or app, we can place printed markers in the environment. The robot uses its camera to detect the marker, reads the marker ID, and then performs a behavior assigned to that ID.

Example:

| Marker ID | Robot Behavior |
|---|---|
| 0 | Stop |
| 1 | Stand up |
| 2 | Sit |
| 3 | Move forward |
| 4 | Turn / search |
| 5 | Pounce or jump-style behavior |
| 6 | Wave |
| 7 | Shake hands |
| 8 | Heart hands / performance gesture |

By the end of the course, students will build a simple autonomous patrol robot. The Go2 will move through a space, scan for ArUco markers, react to the marker IDs, and use built-in obstacle avoidance to help prevent collisions.

---

# Big Project Idea

The project is not just about detecting a black-and-white square.

The real project is:

> Building a visual command system for a mobile robot.

The robot can read signs in its environment and change behavior based on what it sees.

This has several possible use cases:

## 1. Security or Patrol Robot

The Go2 can patrol a room, hallway, lab, or demonstration space. Markers can be placed in different locations to tell the robot what to do.

Examples:

| Location | Marker Purpose |
|---|---|
| Hallway | Continue patrol |
| Restricted area | Stop or alert |
| Charging zone | Stop or sit |
| Demo zone | Perform a gesture |
| Corner | Turn around |

## 2. Classroom Robotics Demo

Students can print markers and immediately see the robot react. This makes computer vision easy to understand because the result is physical.

Examples:

| Student Action | Robot Response |
|---|---|
| Show marker 1 | Robot stands |
| Show marker 2 | Robot sits |
| Show marker 0 | Robot stops |

## 3. Warehouse or Lab Navigation Signs

Markers can be used as low-cost robot-readable signs.

Examples:

| Marker | Meaning |
|---|---|
| Marker 10 | Loading station |
| Marker 11 | Inspection area |
| Marker 12 | Stop zone |
| Marker 13 | Turn-around zone |

## 4. Human-Robot Interaction

A person can show a marker to the robot instead of using a remote controller.

This makes ArUco markers act like a simple visual language between people and robots.

---

# Course Learning Goals

By the end of this course, students should be able to:

1. Explain what an ArUco marker is.
2. Explain what an ArUco dictionary is.
3. Generate and print ArUco markers.
4. Use OpenCV to detect ArUco markers.
5. Read marker IDs from a live camera feed.
6. Connect Python to the Unitree Go2 using WebRTC.
7. Trigger Go2 built-in actions from marker IDs.
8. Add marker confirmation and cooldown logic.
9. Make the Go2 rotate in place to scan for markers.
10. Add slow movement while scanning.
11. Build a patrol state machine.
12. Enable built-in Go2 obstacle avoidance.
13. Add a simple wall/corner recovery behavior.
14. Create a final demonstration where the robot patrols and responds to visual signs.

---

# Required Hardware and Software

## Hardware

- Unitree Go2 robot
- Laptop running Ubuntu or Linux environment
- Printed ArUco markers
- Open floor space for testing
- Optional: tape or stands for placing markers around the room

## Software

- Python
- OpenCV
- NumPy
- unitree_webrtc_connect
- A Python virtual environment
- VS Code or another code editor

---

# Current Working Project Folder

For our setup, the project folder is:

```bash
~/projects/go2_aruco_opencv