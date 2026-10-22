"""
Specter Toolkit - Alpha Keying & Background Transparency Tool
Converts solid white/near-white backgrounds into true RGBA transparency 
with anti-aliasing edge feathering to eliminate white halo artifacts.
"""

import sys
import os
from PIL import Image

def make_transparent(input_path: str = "base_icon.png", 
                     output_path: str = "base_icon_transparent.png", 
                     threshold: int = 240, 
                     feather: int = 15):
    """
    threshold: Brightness level (0-255) above which pixels begin to become transparent.
    feather: Gradient band for soft alpha blending on anti-aliased edges.
    """
    if not os.path.isfile(input_path):
        print(f"[ERROR] Source image not found at: {input_path}")
        sys.exit(1)

    print(f"[*] Loading image: {input_path}")
    img = Image.open(input_path).convert("RGBA")
    pixels = img.load()
    width, height = img.size

    # Range: pixels with min(RGB) >= (threshold - feather) will be keyed
    lower_bound = max(0, threshold - feather)
    
    modified_pixels = 0
    total_pixels = width * height

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            
            # Use the darkest channel as the brightness metric
            min_channel = min(r, g, b)

            if min_channel >= threshold:
                # Fully white background -> 100% transparent
                pixels[x, y] = (255, 255, 255, 0)
                modified_pixels += 1
            elif min_channel > lower_bound:
                # Anti-aliased border pixel -> calculate feathered alpha
                # Scale alpha from 0 (at threshold) to original alpha (at lower_bound)
                alpha_factor = (threshold - min_channel) / float(threshold - lower_bound)
                new_alpha = int(a * alpha_factor)
                pixels[x, y] = (r, g, b, new_alpha)
                modified_pixels += 1

    img.save(output_path, "PNG")
    print(f"[+] Transparent base saved to: {output_path}")
    print(f"    Dimensions     : {width}x{height}")
    print(f"    Keyed Pixels   : {modified_pixels} / {total_pixels} ({(modified_pixels/total_pixels)*100:.1f}%)")

if __name__ == "__main__":
    # Allows passing custom paths or defaults to local base_icon.png
    src = sys.argv[1] if len(sys.argv) > 1 else "base_icon.png"
    dst = sys.argv[2] if len(sys.argv) > 2 else "base_icon_transparent.png"
    make_transparent(src, dst)