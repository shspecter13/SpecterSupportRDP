import os
import sys
import zipfile
from datetime import datetime
from PIL import Image

# Configuration
SOURCE_ICON = "base_icon.png"  # Path to your master 256x256 or 1024x1024 icon
REPO_ROOT   = os.path.abspath(".")
TIMESTAMP   = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_ZIP  = f"RustDesk_Original_Branding_Backup_{TIMESTAMP}.zip"

# Standard Windows .ico resolutions
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# Target extensions
VALID_EXTENSIONS = {".ico", ".png", ".bmp"}

def build_inventory_and_backup(repo_path: str):
    """Crawl repository for branding assets and pack them into a backup zip."""
    targets = []
    print(f"[*] Crawling {repo_path} for branding graphics...")

    with zipfile.ZipFile(BACKUP_ZIP, "w", zipfile.ZIP_DEFLATED) as backup_zip:
        for root, dirs, files in os.walk(repo_path):
            # Exclude build artifacts and git internals
            if any(ignore in root for ignore in [".git", "target", "build", ".dart_tool"]):
                continue

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in VALID_EXTENSIONS:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, repo_path)
                    
                    try:
                        with Image.open(full_path) as img:
                            targets.append({
                                "full_path": full_path,
                                "rel_path": rel_path,
                                "ext": ext,
                                "size": img.size,
                                "mode": img.mode
                            })
                            # Add to backup
                            backup_zip.write(full_path, arcname=rel_path)
                    except Exception as e:
                        # Skip corrupt or non-standard image files
                        pass

    print(f"[+] Successfully backed up {len(targets)} original assets to: {BACKUP_ZIP}")
    return targets

def generate_and_replace(targets, master_image_path: str):
    """Scale master image preserving alpha and overwrite target assets."""
    if not os.path.isfile(master_image_path):
        print(f"[ERROR] Source image not found at: {master_image_path}")
        sys.exit(1)

    print(f"[*] Loading master source image: {master_image_path}")
    master = Image.open(master_image_path).convert("RGBA")

    print(f"[*] Beginning high-quality Lanczos scaling and in-place replacement...")
    replaced_count = 0

    for item in targets:
        target_path = item["full_path"]
        target_ext  = item["ext"]
        target_size = item["size"]

        try:
            if target_ext == ".ico":
                # Compile multi-resolution Windows ICO container
                master.save(target_path, format="ICO", sizes=ICO_SIZES)
                print(f" [+] Replaced ICO (Multi-layer): {item['rel_path']}")
            
            elif target_ext == ".png":
                # Lanczos resize preserving RGBA transparency
                resized = master.resize(target_size, Image.Resampling.LANCZOS)
                resized.save(target_path, format="PNG")
                print(f" [+] Replaced PNG ({target_size[0]}x{target_size[1]}): {item['rel_path']}")

            elif target_ext == ".bmp":
                # Convert to RGB if BMP doesn't support alpha in that context
                resized = master.resize(target_size, Image.Resampling.LANCZOS).convert("RGB")
                resized.save(target_path, format="BMP")
                print(f" [+] Replaced BMP ({target_size[0]}x{target_size[1]}): {item['rel_path']}")

            replaced_count += 1
        except Exception as e:
            print(f" [!] Failed to replace {item['rel_path']}: {e}")

    print(f"\n===========================================================================")
    print(f"[SUCCESS] Rebranding Complete: {replaced_count}/{len(targets)} assets replaced.")
    print(f" Backup Archive: {BACKUP_ZIP}")
    print(f"===========================================================================")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        SOURCE_ICON = sys.argv[1]

    manifest = build_inventory_and_backup(REPO_ROOT)
    generate_and_replace(manifest, SOURCE_ICON)