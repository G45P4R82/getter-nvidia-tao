#!/usr/bin/env python3
"""Create a tiny deterministic YOLO dataset for the YOLO26 adapter smoke test."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def write_split(root: Path, split: str, count: int) -> None:
    image_dir = root / "images" / split
    label_dir = root / "labels" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        image = Image.new("RGB", (256, 256), "#202938")
        draw = ImageDraw.Draw(image)
        left = 32 + index * 8
        top = 48 + index * 5
        right = 144 + index * 8
        bottom = 184 + index * 3
        draw.rectangle((left, top, right, bottom), fill="#31c48d", outline="#faca15", width=3)
        image.save(image_dir / f"sample_{index:03d}.png")
        center_x = ((left + right) / 2) / 256
        center_y = ((top + bottom) / 2) / 256
        width = (right - left) / 256
        height = (bottom - top) / 256
        (label_dir / f"sample_{index:03d}.txt").write_text(
            f"0 {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    write_split(root, "train", 6)
    write_split(root, "val", 2)
    (root / "data.yaml").write_text(
        "path: .\ntrain: images/train\nval: images/val\nnc: 1\nnames: [object]\n",
        encoding="utf-8",
    )
    print(root)


if __name__ == "__main__":
    main()
