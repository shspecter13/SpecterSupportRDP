"""
apply_specter_branding.py

End-to-End Automated Rebranding Engine for SpecterRemote.
Executes Phase 1 (Audit & Manifest), Phase 2 (Archive Backup), and Phase 3 (Lanczos Asset Generation & Deployment).
"""

import os
import sys
import json
import base64
import struct
import zipfile
from io import BytesIO
from datetime import datetime
from PIL import Image

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_ZIP_NAME = f"RustDesk_Original_Branding_Backup_{TIMESTAMP}.zip"
MANIFEST_NAME = "branding_asset_manifest.json"

# Master multi-layer Windows ICO mipmap sizes
STANDARD_ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# Patterns / folders indicating branding assets vs unrelated UI icons / docs
BRANDING_DIRECTORIES = [
    os.path.join("res"),
    os.path.join("flutter", "windows", "runner", "resources"),
    os.path.join("flutter", "android", "app", "src", "main", "res"),
    os.path.join("flutter", "ios", "Runner", "Assets.xcassets", "AppIcon.appiconset"),
    os.path.join("flutter", "assets"),
    os.path.join("fastlane", "metadata", "android", "en-US", "images"),
]

# Specific target files or patterns that are branding assets
BRANDING_TARGET_FILES = {
    # Windows & Linux Backend / Res
    "res/icon.ico": "Windows Manifest / Executable Application Icon",
    "res/tray-icon.ico": "Windows System Tray Icon",
    "res/icon.png": "Master High-Resolution Application Icon (1024x1024)",
    "res/128x128.png": "Linux Desktop Standard Icon (128x128)",
    "res/128x128@2x.png": "Linux Desktop HiDPI Icon (256x256)",
    "res/32x32.png": "Linux Desktop Small Icon (32x32)",
    "res/64x64.png": "Linux Desktop Medium Icon (64x64)",
    "res/mac-icon.png": "macOS Master Application Icon (1024x1024)",
    "res/mac-tray-dark-x2.png": "macOS Menu Bar Tray Dark Mode Icon (60x60)",
    "res/mac-tray-light-x2.png": "macOS Menu Bar Tray Light Mode Icon (48x48)",
    "res/logo.svg": "Vector Application Logo",
    "res/logo-header.svg": "Vector Application Header / Banner Graphic",
    "res/scalable.svg": "Vector Scalable Application Icon",
    "res/design.svg": "Vector Design Master Icon",
    "res/rustdesk-banner.svg": "Vector Branding Banner Graphic",

    # Windows Flutter Runner
    "flutter/windows/runner/resources/app_icon.ico": "Windows Flutter Runner Executable Icon",

    # Flutter Assets
    "flutter/assets/icon.svg": "Flutter UI Application Brand Icon (Vector)",

    # Fastlane / Store Listing
    "fastlane/metadata/android/en-US/images/icon.png": "Android Store Listing Master Icon (256x256)",
}

def determine_purpose(rel_path: str) -> str:
    """Determine the architectural purpose of a branding asset."""
    norm = rel_path.replace("\\", "/")
    if norm in BRANDING_TARGET_FILES:
        return BRANDING_TARGET_FILES[norm]
    
    if "flutter/android/app/src/main/res/mipmap-" in norm:
        fn = os.path.basename(norm)
        if "foreground" in fn:
            return "Android Adaptive Icon Foreground Layer"
        elif "round" in fn:
            return "Android Round Launcher Icon"
        elif "ic_stat" in fn:
            return "Android Notification Status Bar Icon"
        else:
            return "Android Standard App Launcher Icon"

    if "flutter/ios/Runner/Assets.xcassets/AppIcon.appiconset" in norm:
        return "iOS / iPadOS Application Bundle Icon"

    return "Application Branding Asset"

def is_branding_asset(rel_path: str) -> bool:
    """Filter candidate image files to keep only branding/logo/icon/tray assets."""
    norm = rel_path.replace("\\", "/")
    
    # Exclude internal / build / git dirs
    for ignored in [".git", "target", "build", ".dart_tool", "node_modules", "_ico"]:
        if norm.startswith(f"{ignored}/") or f"/{ignored}/" in norm:
            return False

    # Exclude screenshots, docs, and unrelated UI button icons
    if "phoneScreenshots" in norm or "sevenInchScreenshots" in norm:
        return False
    if "libs/clipboard" in norm or "libs/portable" in norm:
        return False
    if norm.startswith("flutter/assets/") and norm != "flutter/assets/icon.svg" and norm != "flutter/assets/icon.png":
        # Keep only the brand icon in flutter/assets, not actions.svg, arrow.svg, scam.png, etc.
        return False

    # Check against known target maps or directories
    if norm in BRANDING_TARGET_FILES:
        return True
    
    if any(norm.startswith(b.replace("\\", "/")) for b in BRANDING_DIRECTORIES):
        return True

    return False

def inspect_ico_dimensions(full_path: str):
    """Parse ICO header to extract all contained frame resolutions."""
    try:
        with open(full_path, "rb") as f:
            data = f.read()
        if len(data) < 6:
            return []
        _, ico_type, count = struct.unpack("<HHH", data[:6])
        if ico_type != 1:
            return []
        frames = []
        offset = 6
        for _ in range(count):
            if offset + 16 > len(data):
                break
            w, h, _, _, _, bpp, _, _ = struct.unpack("<BBBBHHII", data[offset:offset+16])
            w = 256 if w == 0 else w
            h = 256 if h == 0 else h
            frames.append((w, h))
            offset += 16
        return frames
    except Exception:
        return []

def run_phase_1_audit(repo_root: str):
    """PHASE 1: REPOSITORY ASSET AUDIT & INVENTORY"""
    print("\n" + "=" * 80)
    print("PHASE 1: REPOSITORY ASSET AUDIT & INVENTORY")
    print("=" * 80)

    manifest_entries = []

    for root, dirs, files in os.walk(repo_root):
        # Exclude hidden and build directories
        dirs[:] = [d for d in dirs if d not in [".git", "target", "build", ".dart_tool", "node_modules", "_ico"]]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in {".ico", ".png", ".svg", ".bmp"}:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_root).replace("\\", "/")

                if not is_branding_asset(rel_path):
                    continue

                purpose = determine_purpose(rel_path)
                dim_str = "Unknown"
                color_mode = "Unknown"
                has_alpha = False
                frame_sizes = []

                if ext == ".ico":
                    frame_sizes = inspect_ico_dimensions(full_path)
                    if frame_sizes:
                        dim_str = ", ".join([f"{w}x{h}" for w, h in frame_sizes])
                    color_mode = "RGBA (32-bit)"
                    has_alpha = True
                elif ext in {".png", ".bmp"}:
                    try:
                        with Image.open(full_path) as im:
                            dim_str = f"{im.size[0]}x{im.size[1]}"
                            frame_sizes = [im.size]
                            color_mode = im.mode
                            has_alpha = ("A" in im.mode or "transparency" in im.info)
                    except Exception as e:
                        dim_str = f"Error: {e}"
                elif ext == ".svg":
                    dim_str = "Scalable Vector"
                    color_mode = "Vector / XML"
                    has_alpha = True
                    frame_sizes = [(256, 256)]

                entry = {
                    "relative_file_path": rel_path,
                    "format": ext.lstrip(".").upper(),
                    "extension": ext,
                    "dimensions": dim_str,
                    "frame_sizes": frame_sizes,
                    "color_mode": color_mode,
                    "has_alpha_channel": has_alpha,
                    "architectural_purpose": purpose,
                    "file_size_bytes": os.path.getsize(full_path)
                }
                manifest_entries.append(entry)

    manifest_entries.sort(key=lambda x: x["relative_file_path"])
    manifest_path = os.path.join(repo_root, MANIFEST_NAME)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_entries, f, indent=2)

    print(f"[+] Discovered {len(manifest_entries)} primary branding assets across repository.")
    print(f"[+] Emitted clean manifest to: {MANIFEST_NAME}")
    return manifest_entries, manifest_path

def run_phase_2_backup(repo_root: str, manifest: list):
    """PHASE 2: AUTOMATED BACKUP PASS"""
    print("\n" + "=" * 80)
    print("PHASE 2: AUTOMATED BACKUP PASS")
    print("=" * 80)

    backup_path = os.path.join(repo_root, BACKUP_ZIP_NAME)
    print(f"[*] Packaging {len(manifest)} original graphic assets into: {BACKUP_ZIP_NAME}...")

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in manifest:
            rel_path = entry["relative_file_path"]
            full_path = os.path.join(repo_root, rel_path)
            if os.path.isfile(full_path):
                zf.write(full_path, arcname=rel_path)

    # Verification
    if not os.path.isfile(backup_path):
        raise FileNotFoundError(f"[ERROR] Backup archive was not created: {backup_path}")

    backup_size = os.path.getsize(backup_path)
    if backup_size == 0:
        raise ValueError(f"[ERROR] Backup archive is empty (0 bytes): {backup_path}")

    with zipfile.ZipFile(backup_path, "r") as zf:
        archived_files = zf.namelist()

    print(f"[+] Verification Successful!")
    print(f"    - Archive Path: {BACKUP_ZIP_NAME}")
    print(f"    - Archive Size: {backup_size:,} bytes")
    print(f"    - Archived File Count: {len(archived_files)}/{len(manifest)}")

    return backup_path

def create_svg_wrapper(png_image: Image.Image, width: int = 256, height: int = 256) -> str:
    """Wrap a high-res RGBA PNG as an SVG container maintaining transparent alpha."""
    buffer = BytesIO()
    png_image.save(buffer, format="PNG")
    b64_data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}">\n'
        f'  <image width="{width}" height="{height}" xlink:href="data:image/png;base64,{b64_data}" />\n'
        f'</svg>\n'
    )

def run_phase_3_deploy(repo_root: str, manifest: list, master_icon_path: str):
    """PHASE 3: ASSET GENERATION & DEPLOYMENT"""
    print("\n" + "=" * 80)
    print("PHASE 3: ASSET GENERATION & DEPLOYMENT SCRIPT")
    print("=" * 80)

    if not os.path.isfile(master_icon_path):
        raise FileNotFoundError(f"[ERROR] Master source icon not found: {master_icon_path}")

    print(f"[*] Loading master source icon: {master_icon_path}")
    raw_master = Image.open(master_icon_path)
    
    # Enforce strict RGBA color mode so transparent backgrounds are NEVER flattened
    master = raw_master.convert("RGBA")
    print(f"[*] Master image loaded: dimensions={master.size}, mode={master.mode}")

    summary_records = []
    replaced_count = 0

    for item in manifest:
        rel_path = item["relative_file_path"]
        ext = item["extension"]
        full_path = os.path.join(repo_root, rel_path)
        old_size_bytes = os.path.getsize(full_path) if os.path.exists(full_path) else 0

        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        status = "Success"
        confirmed_dim = "N/A"

        try:
            if ext == ".ico":
                # Collect all sizes required: standard desktop mipmaps + any off-standard sizes
                target_sizes = list(STANDARD_ICO_SIZES)
                if item["frame_sizes"]:
                    for sz in item["frame_sizes"]:
                        if sz not in target_sizes:
                            target_sizes.append(sz)
                target_sizes.sort(key=lambda s: s[0])

                # Save multi-layer Windows ICO container with strict RGBA mode
                master.save(full_path, format="ICO", sizes=target_sizes)
                confirmed_dim = ", ".join([f"{w}x{h}" for w, h in target_sizes])

            elif ext == ".png":
                # Target dimensions
                if item["frame_sizes"] and len(item["frame_sizes"]) > 0:
                    target_w, target_h = item["frame_sizes"][0]
                else:
                    target_w, target_h = (256, 256)

                # High-quality Lanczos resampling
                resized = master.resize((target_w, target_h), Image.Resampling.LANCZOS)
                
                # Enforce RGBA transparency preservation
                resized.save(full_path, format="PNG")
                confirmed_dim = f"{target_w}x{target_h}"

            elif ext == ".bmp":
                target_w, target_h = item["frame_sizes"][0] if item["frame_sizes"] else (256, 256)
                resized = master.resize((target_w, target_h), Image.Resampling.LANCZOS)
                resized.save(full_path, format="BMP")
                confirmed_dim = f"{target_w}x{target_h}"

            elif ext == ".svg":
                # Generate clean transparent vector container embedding crisp high-res raster
                svg_content = create_svg_wrapper(master, width=256, height=256)
                with open(full_path, "w", encoding="utf-8") as sf:
                    sf.write(svg_content)
                confirmed_dim = "256x256 (Vector Embedded)"

            new_size_bytes = os.path.getsize(full_path)
            replaced_count += 1
            summary_records.append({
                "path": rel_path,
                "purpose": item["architectural_purpose"],
                "dimensions": confirmed_dim,
                "old_size": old_size_bytes,
                "new_size": new_size_bytes,
                "status": status
            })

        except Exception as e:
            summary_records.append({
                "path": rel_path,
                "purpose": item["architectural_purpose"],
                "dimensions": "Error",
                "old_size": old_size_bytes,
                "new_size": 0,
                "status": f"FAILED: {e}"
            })

    # Also deploy flutter/assets/icon.png if flutter/assets exists (for Flutter loadIcon fallback)
    flutter_assets_icon = os.path.join(repo_root, "flutter", "assets", "icon.png")
    if os.path.isdir(os.path.join(repo_root, "flutter", "assets")):
        master.save(flutter_assets_icon, format="PNG")
        summary_records.append({
            "path": "flutter/assets/icon.png",
            "purpose": "Flutter UI Fallback PNG Icon",
            "dimensions": f"{master.size[0]}x{master.size[1]}",
            "old_size": 0,
            "new_size": os.path.getsize(flutter_assets_icon),
            "status": "Created"
        })

    # Print Summary Table
    print("\n" + "=" * 120)
    print("COMPLETION SUMMARY TABLE: SPECTERREMOTE REBRANDING DEPLOYMENT")
    print("=" * 120)
    fmt = "{:<55} {:<30} {:<15} {:<10}"
    print(fmt.format("Relative File Path", "Confirmed Dimensions", "File Size", "Status"))
    print("-" * 120)
    for r in summary_records:
        path_disp = r["path"] if len(r["path"]) <= 54 else "..." + r["path"][-51:]
        dim_disp = r["dimensions"] if len(r["dimensions"]) <= 29 else r["dimensions"][:26] + "..."
        size_disp = f"{r['new_size']:,} B"
        print(fmt.format(path_disp, dim_disp, size_disp, r["status"]))
    print("=" * 120)
    print(f"\n[SUCCESS] Deployed SpecterRemote branding to {replaced_count}/{len(manifest)} assets.")
    print(f"[+] Master source icon: {master_icon_path}")
    print(f"[+] Backup zip preserved at: {BACKUP_ZIP_NAME}")
    print(f"[+] Asset manifest preserved at: {MANIFEST_NAME}\n")

def find_master_icon(repo_root: str):
    """Locate the master source icon."""
    candidates = [
        os.path.join(repo_root, "base_icon.png"),
        os.path.join(repo_root, "_ico", "app_icon.ico"),
        os.path.join(repo_root, "_ico", "ico_draft.png"),
        os.path.join(repo_root, "app_icon.ico"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

if __name__ == "__main__":
    master_icon = None
    if len(sys.argv) > 1:
        master_icon = os.path.abspath(sys.argv[1])
    else:
        master_icon = find_master_icon(REPO_ROOT)

    if not master_icon or not os.path.isfile(master_icon):
        print(f"[ERROR] Could not find master icon. Please provide path as argument.")
        sys.exit(1)

    print(f"[SPECTERREMOTE REBRANDING ENGINE] Initiating execution from: {REPO_ROOT}")
    print(f"[SPECTERREMOTE REBRANDING ENGINE] Master Source Icon: {master_icon}")

    # Phase 1: Audit & Manifest
    manifest, manifest_path = run_phase_1_audit(REPO_ROOT)

    # Phase 2: Backup
    backup_path = run_phase_2_backup(REPO_ROOT, manifest)

    # Phase 3: Generation & Deployment
    run_phase_3_deploy(REPO_ROOT, manifest, master_icon)
