"""
Specter Toolkit - Strict Solid White Transparency Tool
Converts ONLY exact pure solid white (255, 255, 255) pixels to transparent,
preserving all off-white highlights and interior artwork shades.
"""

import sys
import os
from PIL import Image, ImageDraw

def make_solid_white_transparent(input_path: str = "base_icon.png", 
                                output_path: str = "base_icon_transparent.png",
                                flood_fill: bool = False):
    if not os.path.isfile(input_path):
        print(f"[ERROR] Source image not found at: {input_path}")
        sys.exit(1)

    print(f"[*] Loading image: {input_path}")
    img = Image.open(input_path).convert("RGBA")
    width, height = img.size

    if flood_fill:
        # Mode 1: Flood-Fill from corners (Only removes white touching the outer border)
        print("[*] Mode: Exterior Flood-Fill (Protects any solid white trapped inside the logo)")
        corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
        
        for corner in corners:
            # Only trigger flood fill if corner itself is pure white
            if img.getpixel(corner)[:3] == (255, 255, 255):
                ImageDraw.floodfill(img, corner, (255, 255, 255, 0), thresh=0)
    else:
        # Mode 2: Global Exact Match (Only removes exact 255, 255, 255 across the canvas)
        print("[*] Mode: Strict Exact Match (Only (255, 255, 255) -> 0% alpha)")
        pixels = img.load()
        modified = 0

        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                # Strict pure white check: all three channels must equal 255
                if r == 255 and g == 255 and b == 255:
                    pixels[x, y] = (255, 255, 255, 0)
                    modified += 1

        print(f"    Keyed exact white pixels: {modified} / {width * height}")

    img.save(output_path, "PNG")
    print(f"[+] Transparent base saved to: {output_path}")

if __name__ == "__main__":
    src = "base_icon.png"
    dst = "base_icon_transparent.png"
    use_flood = False

    # Argument handling: python convert_white_to_transparent.py [src] [dst] [--flood]
    for arg in sys.argv[1:]:
        if arg.lower() in ("--flood", "-f"):
            use_flood = True
        elif not os.path.splitext(arg)[1]:
            continue
        elif src == "base_icon.png":
            src = arg
        else:
            dst = arg

    make_solid_white_transparent(src, dst, flood_fill=use_flood)