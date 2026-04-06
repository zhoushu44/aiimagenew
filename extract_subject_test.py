import argparse
import json
import math
from collections import deque
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageChops, ImageFilter, ImageOps

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
DEFAULT_INPUT_DIR = Path(r"E:\360MoveData\Users\Administrator\Desktop\主图收集")
DEFAULT_OUTPUT_DIR = Path(r"E:\360MoveData\Users\Administrator\Desktop\主图收集_主体提取测试")


def iter_images(input_dir: Path) -> Iterable[Path]:
    for path in sorted(input_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def sample_background_color(image: Image.Image) -> Tuple[int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    sample = max(4, min(width, height) // 20)
    patches = [
        (0, 0, sample, sample),
        (width - sample, 0, width, sample),
        (0, height - sample, sample, height),
        (width - sample, height - sample, width, height),
    ]
    pixels = []
    for box in patches:
        region = rgb.crop(box)
        pixels.extend(list(region.getdata()))
    if not pixels:
        return (255, 255, 255)
    pixels.sort()
    mid = pixels[len(pixels) // 2]
    return tuple(int(channel) for channel in mid)


def color_distance(pixel: Tuple[int, int, int], other: Tuple[int, int, int]) -> float:
    return math.sqrt(
        (pixel[0] - other[0]) ** 2
        + (pixel[1] - other[1]) ** 2
        + (pixel[2] - other[2]) ** 2
    )


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def percentile_threshold(image: Image.Image, ratio: float, lower: int, upper: int, default: int) -> int:
    histogram = image.histogram()
    total = sum(histogram)
    if not total:
        return default
    target = total * ratio
    running = 0
    for value, count in enumerate(histogram):
        running += count
        if running >= target:
            return max(lower, min(upper, value))
    return default


def trim_background_bounds(image: Image.Image, bg_color: Tuple[int, int, int]) -> Tuple[int, int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    tolerance = 30

    def row_is_background(y: int) -> bool:
        matches = 0
        for x in range(width):
            if color_distance(pixels[x, y], bg_color) <= tolerance:
                matches += 1
        return matches / max(1, width) >= 0.96

    def col_is_background(x: int) -> bool:
        matches = 0
        for y in range(height):
            if color_distance(pixels[x, y], bg_color) <= tolerance:
                matches += 1
        return matches / max(1, height) >= 0.96

    top = 0
    while top < height // 5 and row_is_background(top):
        top += 1

    bottom = height - 1
    while bottom > height * 4 // 5 and row_is_background(bottom):
        bottom -= 1

    left = 0
    while left < width // 5 and col_is_background(left):
        left += 1

    right = width - 1
    while right > width * 4 // 5 and col_is_background(right):
        right -= 1

    if right <= left or bottom <= top:
        return (0, 0, width, height)
    return (left, top, right + 1, bottom + 1)


def build_subject_mask(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    bg_color = sample_background_color(rgb)
    trim_bounds = trim_background_bounds(rgb, bg_color)
    cropped = rgb.crop(trim_bounds)

    bg = Image.new("RGB", cropped.size, bg_color)
    diff = ImageChops.difference(cropped, bg).convert("L")
    gray = ImageOps.autocontrast(cropped.convert("L"))
    edges = gray.filter(ImageFilter.FIND_EDGES)

    saturation = Image.new("L", cropped.size)
    sat_pixels = []
    for pixel in cropped.getdata():
        sat_pixels.append(max(pixel) - min(pixel))
    saturation.putdata(sat_pixels)

    combined = ImageChops.lighter(diff, edges)
    combined = ImageChops.lighter(combined, saturation)
    combined = ImageOps.autocontrast(combined)

    threshold = percentile_threshold(combined, ratio=0.80, lower=22, upper=96, default=34)
    mask = combined.point(lambda value: 255 if value >= threshold else 0)

    shorter_side = min(cropped.size)
    grow = 2 if shorter_side < 1200 else 3
    shrink = 1 if shorter_side < 1200 else 2
    for _ in range(grow):
        mask = mask.filter(ImageFilter.MaxFilter(5))
    for _ in range(shrink):
        mask = mask.filter(ImageFilter.MinFilter(3))
    mask = mask.filter(ImageFilter.GaussianBlur(radius=1.0)).point(lambda value: 255 if value >= 92 else 0)

    full_mask = Image.new("L", rgb.size, 0)
    full_mask.paste(mask, trim_bounds[:2])
    return full_mask


def find_components(mask: Image.Image) -> List[Dict[str, float]]:
    binary = mask.convert("L")
    width, height = binary.size
    pixels = binary.load()
    visited = bytearray(width * height)
    components: List[Dict[str, float]] = []

    def index(x: int, y: int) -> int:
        return y * width + x

    for y in range(height):
        for x in range(width):
            idx = index(x, y)
            if visited[idx] or pixels[x, y] == 0:
                continue

            queue = deque([(x, y)])
            visited[idx] = 1
            area = 0
            left = right = x
            top = bottom = y
            sum_x = 0.0
            sum_y = 0.0
            touches_border = False

            while queue:
                cx, cy = queue.popleft()
                area += 1
                sum_x += cx
                sum_y += cy
                left = min(left, cx)
                right = max(right, cx)
                top = min(top, cy)
                bottom = max(bottom, cy)
                if cx == 0 or cy == 0 or cx == width - 1 or cy == height - 1:
                    touches_border = True

                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    nidx = index(nx, ny)
                    if visited[nidx] or pixels[nx, ny] == 0:
                        continue
                    visited[nidx] = 1
                    queue.append((nx, ny))

            bbox = (left, top, right + 1, bottom + 1)
            box_w = bbox[2] - bbox[0]
            box_h = bbox[3] - bbox[1]
            if box_w <= 0 or box_h <= 0:
                continue

            components.append(
                {
                    "bbox": bbox,
                    "area": float(area),
                    "width": float(box_w),
                    "height": float(box_h),
                    "center_x": sum_x / area,
                    "center_y": sum_y / area,
                    "touches_border": float(1 if touches_border else 0),
                }
            )
    return components


def score_component(component: Dict[str, float], image_size: Tuple[int, int]) -> float:
    width, height = image_size
    image_area = max(1.0, float(width * height))
    area_ratio = component["area"] / image_area
    width_ratio = component["width"] / max(1.0, width)
    height_ratio = component["height"] / max(1.0, height)

    center_dx = abs(component["center_x"] - width / 2) / max(1.0, width / 2)
    center_dy = abs(component["center_y"] - height / 2) / max(1.0, height / 2)
    center_score = 1.0 - clamp((center_dx * 0.8) + (center_dy * 1.2), 0.0, 1.0)

    aspect = component["width"] / max(1.0, component["height"])
    aspect_penalty = 0.0
    if aspect > 4.5 or aspect < 0.18:
        aspect_penalty += 0.35

    score = 0.0
    score += clamp(area_ratio * 5.5, 0.0, 2.2)
    score += center_score * 1.2
    score += clamp(width_ratio * 0.8, 0.0, 0.6)
    score += clamp(height_ratio * 0.9, 0.0, 0.7)
    score -= component["touches_border"] * 0.45
    score -= aspect_penalty

    return score


def merge_boxes(boxes: List[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int]:
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    bottom = max(box[3] for box in boxes)
    return (left, top, right, bottom)


def expand_bbox(bbox: Tuple[int, int, int, int], image_size: Tuple[int, int], padding_ratio: float = 0.08):
    left, top, right, bottom = bbox
    width, height = image_size
    box_w = right - left
    box_h = bottom - top
    pad_x = max(10, int(box_w * padding_ratio))
    pad_y = max(10, int(box_h * padding_ratio))
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(width, right + pad_x),
        min(height, bottom + pad_y),
    )


def tighten_bbox_by_background(
    image: Image.Image,
    bbox: Tuple[int, int, int, int],
    bg_color: Tuple[int, int, int],
) -> Tuple[int, int, int, int]:
    rgb = image.convert("RGB")
    pixels = rgb.load()
    width, height = rgb.size
    left, top, right, bottom = bbox
    tolerance = 26

    def edge_similarity_vertical(x: int) -> float:
        matches = 0
        total = max(1, bottom - top)
        for y in range(top, bottom):
            if color_distance(pixels[x, y], bg_color) <= tolerance:
                matches += 1
        return matches / total

    def edge_similarity_horizontal(y: int) -> float:
        matches = 0
        total = max(1, right - left)
        for x in range(left, right):
            if color_distance(pixels[x, y], bg_color) <= tolerance:
                matches += 1
        return matches / total

    moved = True
    while moved:
        moved = False
        if left + 4 < right and edge_similarity_vertical(left) >= 0.93:
            left += 1
            moved = True
        if right - 5 > left and edge_similarity_vertical(right - 1) >= 0.93:
            right -= 1
            moved = True
        if top + 4 < bottom and edge_similarity_horizontal(top) >= 0.93:
            top += 1
            moved = True
        if bottom - 5 > top and edge_similarity_horizontal(bottom - 1) >= 0.93:
            bottom -= 1
            moved = True

    return (
        max(0, min(left, width - 1)),
        max(0, min(top, height - 1)),
        max(left + 1, min(right, width)),
        max(top + 1, min(bottom, height)),
    )


def fallback_center_crop(image: Image.Image, crop_ratio: float = 0.72):
    width, height = image.size
    crop_w = int(width * crop_ratio)
    crop_h = int(height * crop_ratio)
    left = max(0, (width - crop_w) // 2)
    top = max(0, (height - crop_h) // 2)
    return (left, top, min(width, left + crop_w), min(height, top + crop_h))


def resolve_subject_bbox(image: Image.Image, mask: Image.Image):
    components = find_components(mask)
    if not components:
        return fallback_center_crop(image), "fallback:no-mask", None

    scored = []
    for component in components:
        component["score"] = score_component(component, image.size)
        scored.append(component)
    scored.sort(key=lambda item: item["score"], reverse=True)

    best = scored[0]
    selected_boxes = [best["bbox"]]
    image_center_x = image.size[0] / 2
    image_center_y = image.size[1] / 2
    best_diag = math.hypot(best["width"], best["height"])

    for component in scored[1:8]:
        if component["score"] < best["score"] * 0.35:
            continue
        distance = math.hypot(component["center_x"] - best["center_x"], component["center_y"] - best["center_y"])
        center_distance = math.hypot(component["center_x"] - image_center_x, component["center_y"] - image_center_y)
        if distance <= best_diag * 0.7 or center_distance <= best_diag * 0.6:
            selected_boxes.append(component["bbox"])

    bbox = merge_boxes(selected_boxes)
    bbox = expand_bbox(bbox, image.size, padding_ratio=0.08)
    bg_color = sample_background_color(image)
    bbox = tighten_bbox_by_background(image, bbox, bg_color)

    crop_w = bbox[2] - bbox[0]
    crop_h = bbox[3] - bbox[1]
    width, height = image.size

    if crop_w >= width * 0.97 and crop_h >= height * 0.97:
        return fallback_center_crop(image), "fallback:full-frame", best
    if crop_w < width * 0.10 or crop_h < height * 0.10:
        return fallback_center_crop(image), "fallback:tiny-box", best

    return bbox, "mask", best


def paste_contain(image: Image.Image, size: Tuple[int, int], background=(245, 245, 245)) -> Image.Image:
    canvas = Image.new("RGB", size, background)
    fitted = ImageOps.contain(image.convert("RGB"), size)
    left = (size[0] - fitted.width) // 2
    top = (size[1] - fitted.height) // 2
    canvas.paste(fitted, (left, top))
    return canvas


def build_preview(original: Image.Image, mask: Image.Image, crop: Image.Image, bbox: Tuple[int, int, int, int]) -> Image.Image:
    panel_w = 420
    panel_h = 420
    gap = 24
    annotated = original.convert("RGB").copy()
    overlay = Image.new("RGBA", annotated.size, (0, 0, 0, 0))
    box = Image.new("RGBA", (bbox[2] - bbox[0], bbox[3] - bbox[1]), (80, 180, 255, 70))
    overlay.paste(box, (bbox[0], bbox[1]))
    annotated = Image.alpha_composite(annotated.convert("RGBA"), overlay).convert("RGB")

    mask_rgb = ImageOps.colorize(mask.convert("L"), black="#111111", white="#F4F4F4")
    left = paste_contain(annotated, (panel_w, panel_h))
    middle = paste_contain(mask_rgb, (panel_w, panel_h))
    right = paste_contain(crop, (panel_w, panel_h))
    preview = Image.new("RGB", (panel_w * 3 + gap * 4, panel_h + gap * 2), (255, 255, 255))
    preview.paste(left, (gap, gap))
    preview.paste(middle, (panel_w + gap * 2, gap))
    preview.paste(right, (panel_w * 2 + gap * 3, gap))
    return preview


def process_image(image_path: Path, output_dir: Path):
    relative_name = image_path.stem
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        mask = build_subject_mask(image)
        bbox, mode, best_component = resolve_subject_bbox(image, mask)
        crop = image.crop(bbox)
        preview = build_preview(image, mask, crop, bbox)

    mask_path = output_dir / "masks" / f"{relative_name}_mask.png"
    crop_path = output_dir / "crops" / f"{relative_name}_subject.png"
    preview_path = output_dir / "previews" / f"{relative_name}_preview.jpg"

    mask_path.parent.mkdir(parents=True, exist_ok=True)
    crop_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    mask.save(mask_path)
    crop.save(crop_path, quality=95)
    preview.save(preview_path, quality=90)

    result = {
        "source": str(image_path),
        "mask": str(mask_path),
        "crop": str(crop_path),
        "preview": str(preview_path),
        "bbox": {"left": bbox[0], "top": bbox[1], "right": bbox[2], "bottom": bbox[3]},
        "mode": mode,
        "source_size": {"width": image.width, "height": image.height},
        "crop_size": {"width": crop.width, "height": crop.height},
    }
    if best_component:
        result["best_component"] = {
            "bbox": {
                "left": int(best_component["bbox"][0]),
                "top": int(best_component["bbox"][1]),
                "right": int(best_component["bbox"][2]),
                "bottom": int(best_component["bbox"][3]),
            },
            "score": round(float(best_component["score"]), 4),
            "area": int(best_component["area"]),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description="批量测试轻量商品主体提取，不写入主代码链路。")
    parser.add_argument("--input", default=str(DEFAULT_INPUT_DIR), help="输入图片目录")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="输出目录")
    parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 张，0 表示全部")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"输入目录不存在：{input_dir}")

    images = list(iter_images(input_dir))
    if args.limit and args.limit > 0:
        images = images[: args.limit]
    if not images:
        raise SystemExit("输入目录中没有可处理图片")

    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "image_count": len(images),
        "results": [],
    }

    for index, image_path in enumerate(images, start=1):
        safe_name = image_path.name.encode("gbk", errors="replace").decode("gbk")
        print(f"[{index}/{len(images)}] processing: {safe_name}")
        result = process_image(image_path, output_dir)
        summary["results"].append(result)

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {summary_path}")


if __name__ == "__main__":
    main()
