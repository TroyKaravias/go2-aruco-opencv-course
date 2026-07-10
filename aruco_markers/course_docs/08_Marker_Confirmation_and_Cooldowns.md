# Module 8: Marker Confirmation and Cooldowns

## Goal

In this module, students learn how to make marker detection more reliable and safer.

The robot should not immediately perform an action every time a marker appears for a single frame.

Instead, the robot should:

1. confirm the marker across multiple frames
2. trigger the action once
3. wait before allowing the same marker to trigger again

This prevents accidental detections and repeated commands.

---

## Why This Module Matters

Camera detection can be noisy.

A marker might appear for only one frame because of:

- motion blur
- poor lighting
- a partial view of the marker
- glare
- fast robot movement
- the marker leaving the camera frame

If the robot immediately reacts to every single detection, it may perform actions accidentally.

Instead, we want reliable behavior.

---

## The Problem Without Confirmation

Imagine the robot sees marker 1 for one frame.

Without confirmation, the code may instantly send the StandUp command.

Example problem:

```text
Frame 1: Marker 1 appears briefly
Python sends StandUp immediately