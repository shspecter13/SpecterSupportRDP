"""
Specter Toolkit - Manifest-Driven Branding Deployment Engine
Parses relative_file_path, frame_sizes, and multi-resolution dimensions
from branding_asset_manifest.json to deploy transparent RGBA assets in-place.
"""

import sys
import os
import json
import re
from PIL import Image

MANIFEST_FILE = "branding_asset_manifest.json"
SOURCE_IMAGE  = "base_icon_transparent.png"
REPO_ROOT     = os.path.abspath(".")

# Fallback Windows ICO mipmaps if an .ico entry does not specify frame_sizes
DEFAULT_ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

def parse_target_info(entry: dict):
    """
    Parses manifest entries matching the exact agent schema:
      - relative_file_path
      - frame_sizes ([[w, h], ...])
      - dimensions ("256x256" or "16x16, 24x24...")
    """
    # 1. Resolve Path
    path_val = (
        entry.get("relative_file_path")
        or entry.get("rel_path")
        or entry.get("path")
        or entry.get("location")
        or entry.get("full_path")
        or entry.get("file_path")
        or entry.get("filename")
    )

    frame_sizes = []

    # 2. Extract frame_sizes array if present ([[256, 256]], [[16, 16], [32, 32]], etc.)
    raw_frames = entry.get("frame_sizes")
    if isinstance(raw_frames, list):
        for f in raw_frames:
            if isinstance(f, (list, tuple)) and len(f) >= 2:
                frame_sizes.append((int(f[0]), int(f[1])))

    # 3. Fallback: Parse dimensions string using regex to handle multi-size strings safely
    if not frame_sizes and "dimensions" in entry:
        dim_str = str(entry["dimensions"])
        # Match all WxH patterns (handles both "256x256" and "16x16, 24x24, 32x32")
        matches = re.findall(r'(\d+)\s*[xX]\s*(\d+)', dim_str)
        for w, h in matches:
            frame_sizes.append((int(w), int(h)))

    # 4. Resolve primary target width & height
    if frame_sizes:
        # Use the largest frame size for single-image targets (PNG / BMP)
        largest_frame = max(frame_sizes, key=lambda s: s[0] * s[1])
        width, height = largest_frame
    else:
        # Fallback to inspecting existing file or default 256
        width, height = (256, 256)
        frame_sizes = DEFAULT_ICO_SIZES

    return path_val, width, height, frame_sizes

def deploy_from_manifest(manifest_path: str, source_path: str, repo_root: str):
    if not os.path.isfile(manifest_path):
        print(f"[ERROR] Manifest file not found at: {manifest_path}")
        sys.exit(1)

    if not os.path.isfile(source_path):
        # Fallback check for base_icon.png if transparent wasn't named
        if os.path.isfile("base_icon.png"):
            source_path = "base_icon.png"
            print(f"[!] Warning: base_icon_transparent.png not found, falling back to: {source_path}")
        else:
            print(f"[ERROR] Source image not found at: {source_path}")
            sys.exit(1)

    print(f"[*] Loading manifest: {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    entries = data if isinstance(data, list) else data.get("assets", data.get("resources", []))

    print(f"[*] Loading master graphic: {source_path}")
    master_img = Image.open(source_path).convert("RGBA")

    print(f"[*] Processing {len(entries)} target assets across repository...\n")
    success_count = 0
    fail_count = 0

    for idx, entry in enumerate(entries, start=1):
        rel_path, width, height, frame_sizes = parse_target_info(entry)

        if not rel_path:
            print(f" [!] [{idx:02d}] Skipped: Could not determine file path.")
            fail_count += 1
            continue

        target_full_path = os.path.join(repo_root, rel_path)
        ext = os.path.splitext(target_full_path)[1].lower()

        # Ensure parent destination directory exists
        os.makedirs(os.path.dirname(target_full_path), exist_ok=True)

        try:
            if ext == ".ico":
                # For ICO, use exact frame sizes from manifest or default standard mipmaps
                ico_sizes_to_use = frame_sizes if len(frame_sizes) > 1 else DEFAULT_ICO_SIZES
                master_img.save(target_full_path, format="ICO", sizes=ico_sizes_to_use)
                sizes_str = ", ".join([f"{w}x{h}" for w, h in ico_sizes_to_use])
                print(f" [+] [{idx:02d}] Deployed ICO ({sizes_str}): {rel_path}")

            elif ext == ".png":
                # High-quality Lanczos scaling preserving true alpha channel
                target_size = (int(width), int(height))
                resized = master_img.resize(target_size, Image.Resampling.LANCZOS)
                resized.save(target_full_path, format="PNG")
                print(f" [+] [{idx:02d}] Deployed PNG ({target_size[0]}x{target_size[1]}): {rel_path}")

            elif ext == ".bmp":
                # Standard BMP fallback (convert to RGB if required by target engine)
                target_size = (int(width), int(height))
                resized = master_img.resize(target_size, Image.Resampling.LANCZOS).convert("RGB")
                resized.save(target_full_path, format="BMP")
                print(f" [+] [{idx:02d}] Deployed BMP ({target_size[0]}x{target_size[1]}): {rel_path}")

            else:
                print(f" [!] [{idx:02d}] Skipped unsupported extension ({ext}): {rel_path}")
                fail_count += 1
                continue

            success_count += 1
        except Exception as e:
            print(f" [ERROR] [{idx:02d}] Failed {rel_path}: {e}")
            fail_count += 1

    print("\n===========================================================================")
    print(f"[SUCCESS] Deployment Complete: {success_count} deployed, {fail_count} skipped/failed.")
    print("===========================================================================")

if __name__ == "__main__":
    manifest = sys.argv[1] if len(sys.argv) > 1 else MANIFEST_FILE
    source   = sys.argv[2] if len(sys.argv) > 2 else SOURCE_IMAGE
    deploy_from_manifest(manifest, source, REPO_ROOT)