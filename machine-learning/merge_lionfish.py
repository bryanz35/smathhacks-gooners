"""
Merge the lionfish classification dataset into the main YOLO detection dataset.

Since the lionfish images have no bounding box annotations, each image gets a
full-image bounding box label (class 13: Lionfish) at [0.5, 0.5, 1.0, 1.0].

Images are renamed to match the existing naming convention:
    lionfish_XXXX_ORIGINALHASH.jpg
"""

import shutil
from pathlib import Path

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
LIONFISH_DIR = BASE / "lionfish" / "data"

# Lionfish class ID (appended after the existing 13 classes, indices 0-12)
LIONFISH_CLASS_ID = 13

# Map lionfish split names to main dataset split names
SPLIT_MAP = {
    "train": "train",
    "val": "valid",
    "test": "test",
}


def merge_split(src_split: str, dst_split: str) -> int:
    src_dir = LIONFISH_DIR / src_split / "lionfish"
    dst_images = DATA_DIR / dst_split / "images"
    dst_labels = DATA_DIR / dst_split / "labels"

    if not src_dir.exists():
        print(f"  Skipping {src_split}: {src_dir} not found")
        return 0

    dst_images.mkdir(parents=True, exist_ok=True)
    dst_labels.mkdir(parents=True, exist_ok=True)

    images = sorted(src_dir.iterdir())
    count = 0

    for idx, img_path in enumerate(images, start=1):
        if not img_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
            continue

        # Rename: lionfish_0001_ORIGINALSTEM.jpg
        new_name = f"lionfish_{idx:04d}_{img_path.stem}{img_path.suffix.lower()}"
        dst_img = dst_images / new_name
        dst_lbl = dst_labels / f"lionfish_{idx:04d}_{img_path.stem}.txt"

        # Copy image
        shutil.copy2(img_path, dst_img)

        # Create YOLO label: full-image bounding box
        dst_lbl.write_text(f"{LIONFISH_CLASS_ID} 0.5 0.5 1.0 1.0\n")

        count += 1

    return count


def update_data_yaml():
    yaml_path = DATA_DIR / "data.yaml"
    text = yaml_path.read_text()

    if "Lionfish" in text:
        print("  data.yaml already contains Lionfish, skipping update")
        return

    # Update class count and names list
    text = text.replace("nc: 13", "nc: 14")
    text = text.replace(
        "'ZebraFish']",
        "'ZebraFish', 'Lionfish']",
    )
    yaml_path.write_text(text)
    print("  Updated data.yaml: added Lionfish as class 13 (nc: 14)")


def main():
    print("Merging lionfish dataset into main YOLO dataset...\n")

    total = 0
    for src_split, dst_split in SPLIT_MAP.items():
        count = merge_split(src_split, dst_split)
        print(f"  {src_split} -> {dst_split}: {count} images merged")
        total += count

    print()
    update_data_yaml()
    print(f"\nDone! Merged {total} lionfish images total.")


if __name__ == "__main__":
    main()
