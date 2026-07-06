# Module 16: Future Improvements and Extensions

## Goal

In this module, students think about how the project could be improved after the first working demo.

The current system is a strong beginner project, but it can be expanded in many directions.

---

## Current System

The current project can:

- connect to the Go2
- receive the camera stream
- detect ArUco markers
- read marker IDs
- trigger Go2 behaviors
- patrol autonomously
- enable built-in obstacle avoidance
- attempt wall/corner recovery

This is a complete beginner-level robotics project.

---

## Current Limitations

The system still has limits.

It does not:

- build a map
- know its exact position
- plan paths
- use full LiDAR navigation
- understand objects besides markers
- estimate marker distance in 3D
- return to a charging dock
- handle every obstacle perfectly

These limitations create opportunities for future work.

---

## Extension 1: Better Marker-Based Navigation

Instead of using markers only for actions, markers could become navigation signs.

Examples:

| Marker ID | Meaning |
|---|---|
| 10 | Turn left |
| 11 | Turn right |
| 12 | Go forward |
| 13 | Stop zone |
| 14 | Patrol checkpoint |
| 15 | Return to start |

This would make the environment more like a robot-readable course.

---

## Extension 2: Marker Pose Estimation

OpenCV can estimate the position and angle of an ArUco marker if the camera is calibrated.

This could let the robot estimate:

```text
how far away the marker is
whether the marker is left or right
the angle of the marker