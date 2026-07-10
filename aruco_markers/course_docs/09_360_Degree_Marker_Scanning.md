# Module 9: 360-Degree Marker Scanning

## Goal

In this module, students make the Go2 search for ArUco markers by rotating in place.

This is the first step toward autonomous behavior.

Before this module, the robot only reacted when a marker was already in front of the camera.

In this module, the robot begins to search on its own.

---

## Why 360-Degree Scanning Comes First

Before making the robot walk around, it is safer to make it rotate in place.

This lets students test autonomous behavior without immediately dealing with forward movement, walls, furniture, or obstacle avoidance.

The behavior is simple:

```text
Robot stands still
        ↓
Robot slowly rotates
        ↓
Camera scans the room
        ↓
Marker appears in camera view
        ↓
Robot stops
        ↓
Robot confirms marker
        ↓
Robot performs marker action