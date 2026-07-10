# Module 5: Go2 Camera and WebRTC Setup

## Goal

In this module, students learn how Python connects to the Unitree Go2 and receives the robot's camera feed.

This is the bridge between the robot and OpenCV.

---

## Why We Need WebRTC

The Go2 camera feed is accessed through WebRTC.

WebRTC is a communication system that allows video, audio, and data to stream between devices.

In this project, we use it for:

```text
Go2 camera video
Go2 data channel
Go2 robot commands