# Module 1: What Is an ArUco Marker?

## Goal

In this module, students learn what an ArUco marker is and why it is useful in robotics.

---

## Simple Explanation

An ArUco marker is a black-and-white square marker that a camera can detect.

Each marker has a unique ID number.

The robot does not just see a square. OpenCV detects the square, decodes the pattern inside it, and tells Python which marker ID was found.

Example:

```text
Camera sees marker
        ↓
OpenCV detects marker
        ↓
OpenCV identifies marker ID
        ↓
Python decides what that ID means
        ↓
Robot performs action