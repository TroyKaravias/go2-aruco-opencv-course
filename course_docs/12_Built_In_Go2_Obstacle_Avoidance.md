# Module 12: Built-In Go2 Obstacle Avoidance

## Goal

In this module, students learn how to use the Go2's built-in obstacle avoidance while the Python script controls patrol behavior.

The goal is not to write custom LiDAR obstacle avoidance yet.

Instead, Python sends cautious movement commands while the Go2's internal system helps avoid obstacles.

---

## Why Use Built-In Obstacle Avoidance First?

Custom obstacle avoidance is more advanced.

It may require:

- LiDAR data
- depth data
- ROS 2 topics
- SLAM
- navigation planning
- custom sensor processing

For the beginner course, it is better to first use the robot's built-in obstacle avoidance.

This lets students focus on:

```text
ArUco detection
marker actions
robot movement
patrol behavior
state machines