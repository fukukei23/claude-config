#!/usr/bin/env python3
"""花鈿（かでん/huadian）を画像処理で除去する。

Usage:
    python3 remove_huadian.py <input.jpg> [output.jpg]

概要:
    AI生成の古代中国女性画像に強制付加される眉間の赤い装飾（花鈿）を、
    画質・表情を維持したまま画像処理で除去する。
    プロンプト制御（NO red dot等のネガティブ指示）は image-01 で無効、
    前髪で物理隠蔽すると画質低下するため、画像処理が最適解。

手法:
    1. OpenCV Haar cascade で顔検出 → 眉間位置（顔上1/3中央）を推定
    2. 眉間周辺で「赤みスコア = min(R-G, R-B)」最大のピクセル群を花鈿マスク化
    3. マスクを膨張し、各ピクセルを周囲肌色（マスク外）の中央値で heal
    4. 境界をガウスぼかしで自然になじませる
"""

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage


def detect_forehead_center(img_rgb: np.ndarray) -> tuple[int, int, int, int]:
    """顔検出から眉間ROI（x0,y0,x1,y1）を返す。失敗時は画像中央帯にフォールバック。

    Args:
        img_rgb: RGB画像配列。

    Returns:
        眉間領域の (x0, y0, x1, y1)。
    """
    h, w, _ = img_rgb.shape
    gray = cv2.cvtColor(img_rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(gray, 1.1, 5)

    if len(faces) == 0:
        # フォールバック: 画像中央上半分
        return (int(w * 0.35), int(h * 0.15), int(w * 0.65), int(h * 0.45))

    # 最大の顔を採用
    fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    # 眉間 = 顔中心x、顔上1/3（額〜眉）の中央y
    cx = fx + fw // 2
    y_top = fy + int(fh * 0.15)
    y_bot = fy + int(fh * 0.45)
    half_w = int(fw * 0.18)
    return (cx - half_w, y_top, cx + half_w, y_bot)


def build_huadian_mask(img_rgb: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    """眉間ROI内の花鈿（高赤み）マスクを構築する。

    Args:
        img_rgb: RGB画像配列。
        roi: (x0, y0, x1, y1)。

    Returns:
        花鈿マスク（bool配列、全体サイズ）。
    """
    h, w, _ = img_rgb.shape
    r = img_rgb[:, :, 0].astype(int)
    g = img_rgb[:, :, 1].astype(int)
    b = img_rgb[:, :, 2].astype(int)
    reddiff = np.minimum(r - g, r - b)

    x0, y0, x1, y1 = roi
    ys, xs = np.indices((h, w))
    in_roi = (ys >= y0) & (ys <= y1) & (xs >= x0) & (xs <= x1)

    # ROI内の赤み分布から動的に閾値を決定（上位を花鈿とみなす）
    roi_diffs = reddiff[in_roi]
    if roi_diffs.size == 0:
        return np.zeros((h, w), dtype=bool)
    threshold = max(55, int(np.percentile(roi_diffs, 98)))

    mask = in_roi & (reddiff > threshold)
    # 小さすぎるノイズ除外
    labeled, n = ndimage.label(mask)
    if n > 0:
        sizes = ndimage.sum(mask, labeled, range(1, n + 1))
        # 最大クラスタとその近傍のみ残す（顔中心寄りの密集）
        keep = sizes >= max(5, sizes.max() * 0.2)
        keep_ids = np.where(keep)[0] + 1
        mask = np.isin(labeled, keep_ids)
    return mask


def heal_mask(img_rgb: np.ndarray, mask: np.ndarray, radius: int = 10) -> np.ndarray:
    """マスク領域を周囲肌色の中央値で埋める。

    Args:
        img_rgb: 元RGB画像（int配列）。
        mask: bool配列。Trueのピクセルをheal。
        radius: サンプリング半径。

    Returns:
        heal後のRGB画像（int配列）。
    """
    h, w, _ = img_rgb.shape
    not_mask = ~mask
    filled = img_rgb.copy()
    ys_m, xs_m = np.where(mask)
    for ym, xm in zip(ys_m, xs_m):
        y0, y1 = max(0, ym - radius), min(h, ym + radius + 1)
        x0, x1 = max(0, xm - radius), min(w, xm + radius + 1)
        sub_not = not_mask[y0:y1, x0:x1]
        sub_rgb = filled[y0:y1, x0:x1]
        for c in range(3):
            chan = sub_rgb[:, :, c][sub_not]
            if len(chan):
                filled[ym, xm, c] = int(np.median(chan))
    return filled


def remove_huadian(input_path: str, output_path: str) -> dict:
    """花鈿を除去して保存し、統計情報を返す。

    Args:
        input_path: 入力画像パス。
        output_path: 出力画像パス。

    Returns:
        結果辞書（face_detected, mask_pixels, remaining_pixels, roi）。
    """
    img = Image.open(input_path).convert("RGB")
    arr = np.array(img).astype(int)

    roi = detect_forehead_center(arr)
    mask = build_huadian_mask(arr, roi)
    mask_pixels = int(mask.sum())

    struct = ndimage.generate_binary_structure(2, 2)
    mask_d = ndimage.binary_dilation(mask, structure=struct, iterations=3)

    filled = heal_mask(arr, mask_d, radius=10)

    # 境界をガウスぼかし（マスク内のみ適用）
    filled_img = Image.fromarray(filled.astype(np.uint8))
    blurred = filled_img.filter(ImageFilter.GaussianBlur(radius=1.5))
    blurred_a = np.array(blurred).astype(int)
    result_a = np.where(mask_d[..., None], blurred_a, arr).astype(np.uint8)
    Image.fromarray(result_a).save(output_path, quality=95)

    # 検証: 修正後のROIに強赤が残っていないか
    r = result_a[:, :, 0].astype(int)
    g = result_a[:, :, 1].astype(int)
    b = result_a[:, :, 2].astype(int)
    reddiff = np.minimum(r - g, r - b)
    h, w, _ = result_a.shape
    ys, xs = np.indices((h, w))
    x0, y0, x1, y1 = roi
    remaining = int(
        ((ys >= y0) & (ys <= y1) & (xs >= x0) & (xs <= x1) & (reddiff > 55)).sum()
    )

    return {
        "roi": roi,
        "mask_pixels": mask_pixels,
        "remaining_pixels": remaining,
        "output": output_path,
    }


def main() -> int:
    """CLI エントリポイント。

    Returns:
        終了コード。
    """
    if len(sys.argv) < 2:
        print("Usage: python3 remove_huadian.py <input.jpg> [output.jpg]")
        return 1

    input_path = sys.argv[1]
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        p = Path(input_path)
        output_path = str(p.with_name(f"{p.stem}_no-huadian{p.suffix}"))

    result = remove_huadian(input_path, output_path)
    print(f"ROI: {result['roi']}")
    print(f"花鈿マスク: {result['mask_pixels']}px")
    print(f"修正後残赤: {result['remaining_pixels']}px")
    print(f"保存: {result['output']}")
    if result["mask_pixels"] == 0:
        print("⚠ 花鈿を検出できませんでした（顔検出失敗または赤点なし）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
