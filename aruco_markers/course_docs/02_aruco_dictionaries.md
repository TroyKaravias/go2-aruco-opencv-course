# Module 2: ArUco Dictionaries and Marker IDs

## Goal

In this module, students learn what an ArUco dictionary is, why marker IDs matter, and why the marker generator and marker detector must use the same dictionary.

---

## What Is an ArUco Dictionary?

An ArUco dictionary is a collection of possible marker patterns.

Each marker pattern has an ID number.

When we create or detect ArUco markers, we need to choose a dictionary.

For example, one dictionary may contain 50 possible markers. Another dictionary may contain 250 possible markers. Another may use a larger internal pattern.

The dictionary tells OpenCV:

> These are the marker patterns you should look for.

---

## Dictionary Used in This Course

In this course, we use:

```python
cv2.aruco.DICT_4X4_50