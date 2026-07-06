# Module 7: Marker-Controlled Go2 Actions

## Goal

In this module, students connect ArUco marker IDs to real Unitree Go2 behaviors.

Up to this point, the project can detect markers and print their IDs. Now we make the robot respond.

The main idea is:

```text
OpenCV detects marker ID
        ↓
Python checks the ID
        ↓
Python chooses a robot command
        ↓
Go2 performs the action