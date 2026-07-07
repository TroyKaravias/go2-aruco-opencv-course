import argparse
import os

import cv2
import numpy as np


def build_print_html(png_filename, size_in, title):
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{title}</title>
  <style>
    @page {{
      size: {size_in}in {size_in}in;
      margin: 0;
    }}

    html, body {{
      margin: 0;
      width: {size_in}in;
      height: {size_in}in;
      background: white;
      overflow: hidden;
    }}

    .sheet {{
      width: {size_in}in;
      height: {size_in}in;
      display: grid;
      place-items: center;
      background: white;
    }}

    img {{
      width: {size_in}in;
      height: {size_in}in;
      image-rendering: pixelated;
      display: block;
    }}
  </style>
</head>
<body>
  <div class=\"sheet\">
    <img src=\"{png_filename}\" alt=\"{title}\" />
  </div>
</body>
</html>
"""


def build_letter_print_html(png_filename, size_in, title):
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{title} (Letter)</title>
  <style>
    @page {{
      size: Letter;
      margin: 0;
    }}

    html, body {{
      margin: 0;
      width: 8.5in;
      height: 11in;
      background: white;
      overflow: hidden;
    }}

    .sheet {{
      width: 8.5in;
      height: 11in;
      display: grid;
      place-items: center;
      background: white;
    }}

    img {{
      width: {size_in}in;
      height: {size_in}in;
      image-rendering: pixelated;
      display: block;
    }}
  </style>
</head>
<body>
  <div class=\"sheet\">
    <img src=\"{png_filename}\" alt=\"{title}\" />
  </div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate one print-ready ArUco marker at an exact physical size "
            "(default 5.5 x 5.5 inches)."
        )
    )
    parser.add_argument("--id", type=int, required=True, help="ArUco marker ID (0-49).")
    parser.add_argument("--size-in", type=float, default=5.5, help="Physical marker size in inches.")
    parser.add_argument("--dpi", type=int, default=300, help="Output raster DPI.")
    parser.add_argument(
        "--dict",
        default="DICT_4X4_50",
        choices=["DICT_4X4_50"],
        help="ArUco dictionary to use.",
    )
    parser.add_argument(
        "--output-dir",
        default="aruco_markers/printables",
        help="Folder where printable files are written.",
    )

    args = parser.parse_args()

    if args.id < 0 or args.id > 49:
        raise ValueError("Marker ID must be in the DICT_4X4_50 range: 0-49.")

    if args.size_in <= 0:
        raise ValueError("--size-in must be greater than zero.")

    if args.dpi <= 0:
        raise ValueError("--dpi must be greater than zero.")

    size_px = int(round(args.size_in * args.dpi))

    if size_px < 200:
        raise ValueError("Requested size is too small. Increase --size-in or --dpi.")

    os.makedirs(args.output_dir, exist_ok=True)

    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, args.id, size_px)

    # Keep output 3-channel so image viewers/printers are consistent.
    marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

    stem = f"aruco_4x4_50_id_{args.id}_{args.size_in:.2f}in_{args.dpi}dpi"
    png_name = f"{stem}.png"
    png_path = os.path.join(args.output_dir, png_name)
    html_path = os.path.join(args.output_dir, f"{stem}.html")
    letter_html_path = os.path.join(args.output_dir, f"{stem}_letter.html")

    ok = cv2.imwrite(png_path, marker_bgr)
    if not ok:
        raise RuntimeError(f"Failed to write marker image to {png_path}")

    html = build_print_html(
        png_filename=png_name,
        size_in=args.size_in,
        title=f"ArUco ID {args.id} ({args.size_in:.2f}in)",
    )
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    letter_html = build_letter_print_html(
      png_filename=png_name,
      size_in=args.size_in,
      title=f"ArUco ID {args.id} ({args.size_in:.2f}in)",
    )
    with open(letter_html_path, "w", encoding="utf-8") as f:
      f.write(letter_html)

    print(f"Saved PNG:  {png_path}")
    print(f"Saved HTML: {html_path}")
    print(f"Saved HTML: {letter_html_path}")
    print(
        "Print tip: open the HTML file in a browser and print with scale=100% "
        "(Actual Size)."
    )


if __name__ == "__main__":
    main()
