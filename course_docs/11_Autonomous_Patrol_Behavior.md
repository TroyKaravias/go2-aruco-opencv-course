# Module 11: Autonomous Patrol Behavior

## Goal

In this module, students turn the Go2 from a simple moving scanner into a basic autonomous patrol robot.

Before this module, the robot could move slowly while scanning for ArUco markers.

In this module, the robot follows a repeated patrol pattern.

---

## Patrol Behavior

The robot cycles through three main states:

```text
FORWARD
SCAN
TURN