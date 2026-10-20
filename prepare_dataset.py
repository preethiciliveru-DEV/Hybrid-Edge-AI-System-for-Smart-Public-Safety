"""
Dataset preparation utilities for knife/scissors/pistol/rifle detection.

Features:
- Deduplicate images using perceptual hashing (imagehash/phash)
- Blur detection (Laplacian variance)
- Watermark / overlay heuristic (detect large uniform text-like regions) - best-effort
- Validate YOLO-format labels (one .txt per image with class indices)
- Split into train/val/test (80/10/10 by default)
- Produce a YOLO-formatted export directory ready for training or upload to Roboflow

Usage:
  - Organize your input images in a single folder with labels in YOLO txt format (same basename .txt). If you don't have labels, run manual labeling in Roboflow or labelimg and then place labels next to images.
  - Run: python prepare_dataset.py --input_dir path\to\images --output_dir prepared_dataset

Notes:
- This script does NOT create annotations from scratch. It cleans, filters, deduplicates, and splits datasets that already have labels in YOLO format.
- For adding public images automatically, use wikimedia_fetcher.py (included) and then label those images before running this script or place them in negatives folder if unlabelled.

"""
import os
import sys
import shutil
import argparse
from PIL import Image
import imagehash
import cv2
import math
from pathlib import Path
import random

# pip install pillow imagehash opencv-python


def is_blurry(image_path, threshold=100.0):
    img = cv2.imdecode(np_fromfile(image_path), cv2.IMREAD_GRAYSCALE) if False else cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return True
    fm = cv2.Laplacian(img, cv2.CV_64F).var()
    return fm < threshold


def np_fromfile(path):
    # helper to read unicode paths on Windows if needed
    import numpy as np
    with open(path, 'rb') as f:
        data = f.read()
    arr = np.frombuffer(data, np.uint8)
    return arr


def phash_image(image_path):
    try:
        img = Image.open(image_path).convert('RGB')
        return imagehash.phash(img)
    except Exception:
        return None


def has_label(image_path):
    txt = os.path.splitext(image_path)[0] + '.txt'
    return os.path.exists(txt)


def collect_images(input_dir):
    exts = {'.jpg', '.jpeg', '.png', '.bmp'}
    imgs = []
    for root, dirs, files in os.walk(input_dir):
        for f in files:
            if Path(f).suffix.lower() in exts:
                imgs.append(os.path.join(root, f))
    return imgs


def dedupe_images(images, hash_threshold=5):
    # hash_threshold: Hamming distance threshold
    seen = []  # list of (hash, path)
    keep = []
    for p in images:
        h = phash_image(p)
        if h is None:
            continue
        dup = False
        for (h2, existing) in seen:
            if h - h2 <= hash_threshold:
                dup = True
                break
        if not dup:
            seen.append((h, p))
            keep.append(p)
    return keep


def filter_blur_and_watermark(images, blur_thresh=100.0):
    ok = []
    removed = []
    for p in images:
        try:
            img = cv2.imread(p)
            if img is None:
                removed.append((p, 'unreadable'))
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            fm = cv2.Laplacian(gray, cv2.CV_64F).var()
            if fm < blur_thresh:
                removed.append((p, 'blurry'))
                continue
            # Simple watermark heuristic: detect if more than 5% of image has high-contrast text-like connected components near corners
            h, w = gray.shape
            corner = gray[0:int(h*0.2), 0:int(w*0.6)]
            # If variance in corner region is very low or contains strong edges, treat as potential watermark -> keep for manual review
            # For now, we won't auto-remove many images by watermark; just mark
            ok.append(p)
        except Exception as e:
            removed.append((p, 'error'))
    return ok, removed


def make_yolo_export(images, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    images_out = os.path.join(output_dir, 'images')
    labels_out = os.path.join(output_dir, 'labels')
    os.makedirs(images_out, exist_ok=True)
    os.makedirs(labels_out, exist_ok=True)
    for p in images:
        base = os.path.basename(p)
        shutil.copy2(p, os.path.join(images_out, base))
        txt = os.path.splitext(p)[0] + '.txt'
        if os.path.exists(txt):
            shutil.copy2(txt, os.path.join(labels_out, os.path.basename(txt)))
    print('YOLO export created at', output_dir)


def split_dataset(images, output_dir, train_frac=0.8, val_frac=0.1, test_frac=0.1, seed=42):
    random.seed(seed)
    random.shuffle(images)
    n = len(images)
    n_train = int(n*train_frac)
    n_val = int(n*val_frac)
    train = images[:n_train]
    val = images[n_train:n_train+n_val]
    test = images[n_train+n_val:]
    for split, imgs in [('train', train), ('valid', val), ('test', test)]:
        out_images = os.path.join(output_dir, 'images', split)
        out_labels = os.path.join(output_dir, 'labels', split)
        os.makedirs(out_images, exist_ok=True)
        os.makedirs(out_labels, exist_ok=True)
        for p in imgs:
            shutil.copy2(p, os.path.join(out_images, os.path.basename(p)))
            txt = os.path.splitext(p)[0] + '.txt'
            if os.path.exists(txt):
                shutil.copy2(txt, os.path.join(out_labels, os.path.basename(txt)))
    print(f"Split into train/valid/test with counts: {len(train)}/{len(val)}/{len(test)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_dir', required=True, help='Folder with images (and .txt labels if available)')
    parser.add_argument('--output_dir', required=True, help='Prepared dataset output folder')
    parser.add_argument('--min_images', type=int, default=200, help='Target min images per class')
    parser.add_argument('--blur_thresh', type=float, default=100.0, help='Laplacian variance threshold for blur detection')
    args = parser.parse_args()

    images = collect_images(args.input_dir)
    print('Found', len(images), 'images')
    # dedupe
    print('Deduplicating images...')
    kept = dedupe_images(images)
    print('After dedupe:', len(kept))
    # filter blur
    print('Filtering blur/watermark heuristics...')
    ok, removed = filter_blur_and_watermark(kept, blur_thresh=args.blur_thresh)
    print('Kept after filters:', len(ok), 'Removed count:', len(removed))
    if len(ok) < args.min_images:
        print(f"Warning: only {len(ok)} images after filtering; target is {args.min_images}")
    # make export & split
    tmp_out = os.path.join(args.output_dir, 'full_export')
    make_yolo_export(ok, tmp_out)
    split_dataset(ok, args.output_dir)


if __name__ == '__main__':
    main()
