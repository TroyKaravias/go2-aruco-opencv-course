import cv2
import os

output_dir = "aruco_markers"
os.makedirs(output_dir, exist_ok=True)

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

marker_size_pixels = 800

for marker_id in range(9):
    marker_img = cv2.aruco.generateImageMarker(
        aruco_dict,
        marker_id,
        marker_size_pixels
    )

    filename = os.path.join(output_dir, f"aruco_4x4_50_id_{marker_id}.png")
    cv2.imwrite(filename, marker_img)
    print(f"Saved {filename}")
