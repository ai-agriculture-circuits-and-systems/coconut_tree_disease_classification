#!/usr/bin/env python3
"""
Convert coconut tree disease classification dataset annotations to COCO JSON format.
Supports multi-class classification (5 disease classes).
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image

def read_split_list(split_file: Path) -> List[str]:
    """Read image base names (without extension) from a split file."""
    if not split_file.exists():
        return []
    lines = [line.strip() for line in split_file.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line]

def image_size(image_path: Path) -> Tuple[int, int]:
    """Return (width, height) for an image path using PIL."""
    with Image.open(image_path) as img:
        return img.width, img.height

def parse_csv_boxes(csv_path: Path) -> List[Dict]:
    """Parse a single CSV file and return bounding boxes with category IDs."""
    if not csv_path.exists():
        return []
    
    boxes = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                x = float(row.get('x', 0))
                y = float(row.get('y', 0))
                width = float(row.get('width', 0))
                height = float(row.get('height', 0))
                label = int(row.get('label', 1))
                
                if width > 0 and height > 0:
                    boxes.append({
                        'bbox': [x, y, width, height],
                        'area': width * height,
                        'category_id': label
                    })
            except (ValueError, KeyError):
                continue
    
    return boxes

def collect_annotations_for_split(
    category_root: Path,
    split: str,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Collect COCO dictionaries for images, annotations, and categories.
    Supports structure: coconut_trees/{subcategory}/ subdirectories.
    """
    sets_dir = category_root / "sets"
    split_file = sets_dir / f"{split}.txt"
    image_stems = set(read_split_list(split_file))
    
    if not image_stems:
        # Fall back to all images if no split file
        image_stems = set()
        for subcat_dir in category_root.glob("*"):
            if subcat_dir.is_dir() and subcat_dir.name != "sets" and subcat_dir.name != "labelmap.json":
                images_dir = subcat_dir / "images"
                if images_dir.exists():
                    image_stems.update({p.stem for p in images_dir.glob("*.png")})
                    image_stems.update({p.stem for p in images_dir.glob("*.jpg")})
                    image_stems.update({p.stem for p in images_dir.glob("*.JPG")})
                    image_stems.update({p.stem for p in images_dir.glob("*.bmp")})
    
    images: List[Dict] = []
    anns: List[Dict] = []
    categories: List[Dict] = [
        {"id": 1, "name": "bud_root_dropping", "supercategory": "coconut_tree"},
        {"id": 2, "name": "bud_rot", "supercategory": "coconut_tree"},
        {"id": 3, "name": "gray_leaf_spot", "supercategory": "coconut_tree"},
        {"id": 4, "name": "leaf_rot", "supercategory": "coconut_tree"},
        {"id": 5, "name": "stem_bleeding", "supercategory": "coconut_tree"}
    ]
    
    image_id_counter = 1
    ann_id_counter = 1
    
    # Check all subcategory directories
    subcategory_names = ['bud_root_dropping', 'bud_rot', 'gray_leaf_spot', 'leaf_rot', 'stem_bleeding']
    
    for stem in sorted(image_stems):
        # Try each subcategory directory
        img_path = None
        subcategory = None
        csv_path = None
        
        for subcat_name in subcategory_names:
            subcat_dir = category_root / subcat_name
            for ext in ['.png', '.jpg', '.JPG', '.PNG', '.bmp', '.BMP']:
                test_path = subcat_dir / 'images' / f"{stem}{ext}"
                if test_path.exists():
                    img_path = test_path
                    subcategory = subcat_name
                    csv_path = subcat_dir / 'csv' / f"{stem}.csv"
                    break
            if img_path:
                break
        
        if not img_path:
            continue
        
        width, height = image_size(img_path)
        images.append({
            "id": image_id_counter,
            "file_name": f"coconut_trees/{subcategory}/images/{img_path.name}",
            "width": width,
            "height": height,
        })
        
        if csv_path and csv_path.exists():
            for box in parse_csv_boxes(csv_path):
                anns.append({
                    "id": ann_id_counter,
                    "image_id": image_id_counter,
                    "category_id": box['category_id'],
                    "bbox": box['bbox'],
                    "area": box['area'],
                    "iscrowd": 0,
                })
                ann_id_counter += 1
        
        image_id_counter += 1
    
    return images, anns, categories

def build_coco_dict(
    images: List[Dict],
    anns: List[Dict],
    categories: List[Dict],
    description: str,
) -> Dict:
    """Build a complete COCO dict from components."""
    return {
        "info": {
            "year": 2025,
            "version": "1.0.0",
            "description": description,
            "url": "",
        },
        "images": images,
        "annotations": anns,
        "categories": categories,
        "licenses": [],
    }

def convert(
    root: Path,
    out_dir: Path,
    category: str,
    splits: List[str],
) -> None:
    """Convert selected category and splits to COCO JSON files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    
    category_root = root / category
    
    for split in splits:
        images, anns, categories = collect_annotations_for_split(
            category_root, split
        )
        desc = f"Coconut Tree Disease Classification {category} {split} split"
        coco = build_coco_dict(images, anns, categories, desc)
        out_path = out_dir / f"{category}_instances_{split}.json"
        out_path.write_text(json.dumps(coco, indent=2), encoding="utf-8")
        print(f"Generated: {out_path} ({len(images)} images, {len(anns)} annotations)")

def main():
    parser = argparse.ArgumentParser(description="Convert coconut tree disease classification annotations to COCO JSON")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Dataset root directory",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory for COCO JSON files (default: <root>/annotations)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default="coconut_trees",
        help="Category name (default: coconut_trees)",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "val", "test"],
        choices=["train", "val", "test", "all"],
        help="Dataset splits to generate (default: train val test)",
    )
    
    args = parser.parse_args()
    
    if args.out is None:
        args.out = args.root / "annotations"
    
    convert(
        root=args.root,
        out_dir=args.out,
        category=args.category,
        splits=args.splits,
    )

if __name__ == "__main__":
    main()

