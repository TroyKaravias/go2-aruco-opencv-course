# Module 10: Movement While Scanning

## Goal

In this module, students add slow movement while the Go2 scans for ArUco markers.

This is the next step after 360-degree scanning.

Before this module, the robot could rotate in place and look for markers.

In this module, the robot begins to move through the environment while still looking for markers.

---

## Why This Module Matters

A robot that only spins in place can scan its surroundings, but it cannot explore.

To explore a room, the Go2 needs to move.

However, movement should be added slowly and carefully.

The goal is not full autonomy yet.

The goal is:

```text
Move slowly
Scan continuously
Stop when a marker appears
React to the marker