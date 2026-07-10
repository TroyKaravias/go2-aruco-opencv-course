# Module 13: Wall and Corner Recovery

## Goal

In this module, students add a simple recovery behavior for when the robot gets blocked near a wall or corner.

The Go2 may be commanded to walk forward, but built-in obstacle avoidance may stop it from moving.

If the patrol code keeps asking the robot to go forward, the robot can appear stuck.

---

## The Problem

During testing, the Go2 could sometimes get stuck near a wall.

The robot was still receiving forward commands, but it was not actually moving forward.

This can happen because:

```text
Python says: move forward
Go2 obstacle avoidance says: obstacle ahead
Robot does not move much
Python keeps saying: move forward