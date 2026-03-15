"""
Generate a confusion matrix heatmap from the CSV in output-yolo/.

Usage:
    pip install seaborn matplotlib pandas
    python conf_matrix_gen.py
    python conf_matrix_gen.py --csv output-yolo/confusion_matrix.csv
    python conf_matrix_gen.py --normalize   # show percentages instead of counts
"""

import argparse
from pathlib import Path

import pandas as pd
import seaborn as sns
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = Path(__file__).parent / "output-yolo"


def main():
    parser = argparse.ArgumentParser(description="Generate confusion matrix heatmap")
    parser.add_argument("--csv", type=str,
                        default=str(OUTPUT_DIR / "confusion_matrix.csv"),
                        help="Path to confusion_matrix.csv")
    parser.add_argument("--normalize", action="store_true",
                        help="Normalize rows to show percentages")
    parser.add_argument("--out", type=str, default=None,
                        help="Output image path (default: next to CSV)")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: {csv_path} not found. Run test_model.py first.")
        return

    df = pd.read_csv(csv_path, index_col=0)

    if args.normalize:
        row_sums = df.sum(axis=1)
        df = df.div(row_sums, axis=0).fillna(0) * 100
        fmt = ".1f"
        cbar_label = "Percent (%)"
    else:
        fmt = "d"
        cbar_label = "Count"

    fig, ax = plt.subplots(figsize=(14, 11))
    sns.heatmap(
        df,
        annot=True,
        fmt=fmt,
        cmap="Blues",
        linewidths=0.5,
        ax=ax,
        cbar_kws={"label": cbar_label},
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Ground Truth")
    ax.set_title("Confusion Matrix" + (" (normalized)" if args.normalize else ""))
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    fig.tight_layout()

    if args.out:
        out_path = Path(args.out)
    else:
        suffix = "_normalized" if args.normalize else ""
        out_path = csv_path.parent / f"confusion_matrix{suffix}.png"

    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved confusion matrix to {out_path}")


if __name__ == "__main__":
    main()
