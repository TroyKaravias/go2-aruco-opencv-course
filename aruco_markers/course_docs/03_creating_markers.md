# Module 3: Creating and Printing ArUco Markers

## Goal

In this module, students learn how to create ArUco marker images, save them, print them, and prepare them for testing with the Unitree Go2 camera.

---

## Why We Need to Create Markers

Before the Go2 can react to ArUco markers, we need physical markers that the camera can see.

Each printed marker has an ID.

That ID becomes a robot command.

Example:

| Marker ID | Robot Behavior |
|---|---|
| 0 | Stop |
| 1 | Stand |
| 2 | Sit |
| 3 | Move forward |
| 4 | Turn or scan |

---

## Marker Dictionary Reminder

For this course, we use:

```python
cv2.aruco.DICT_4X4_50