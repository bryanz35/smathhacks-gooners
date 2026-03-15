import os
import matplotlib.pyplot as plt
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CLASS_NAMES = [
    "AngelFish", "BlueTang", "ButterflyFish", "ClownFish", "GoldFish",
    "Gourami", "MorishIdol", "PlatyFish", "RibbonedSweetlips",
    "ThreeStripedDamselfish", "YellowCichlid", "YellowTang", "ZebraFish",
    "Lionfish",
]

counts = Counter()
for split in ("train", "valid", "test"):
    label_dir = os.path.join(DATA_DIR, split, "labels")
    if not os.path.isdir(label_dir):
        continue
    for fname in os.listdir(label_dir):
        if not fname.endswith(".txt"):
            continue
        with open(os.path.join(label_dir, fname)) as f:
            for line in f:
                cls_id = int(line.split()[0])
                counts[cls_id] += 1

ids = sorted(counts.keys())
names = [CLASS_NAMES[i] if i < len(CLASS_NAMES) else str(i) for i in ids]
values = [counts[i] for i in ids]

plt.figure(figsize=(12, 6))
bars = plt.bar(names, values, color="steelblue", edgecolor="black")
plt.xlabel("Class")
plt.ylabel("Number of Annotations")
plt.title("Label Frequency Across All Splits (Train / Valid / Test)")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()

for bar, val in zip(bars, values):
    plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
             str(val), ha="center", va="bottom", fontsize=8)

plt.savefig(os.path.join(os.path.dirname(__file__), "label_histogram.png"), dpi=150)
plt.show()
print("Saved to label_histogram.png")
