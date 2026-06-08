import argparse
import csv
import json
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("GLOG_minloglevel", "2")

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


DEFAULT_DATASET_DIR = Path(__file__).resolve().parent / "object_dataset5"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "model" / "object_08.tflite"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

NO_DETECTION_LABEL = "__NO_DETECTION__"
LOW_IOU_LABEL = "__LOW_IOU__"
ERROR_LABEL = "__ERROR__"
SPECIAL_LABELS = {NO_DETECTION_LABEL, LOW_IOU_LABEL, ERROR_LABEL}


@dataclass(frozen=True)
class GroundTruth:
    split: str
    image_path: Path
    image_id: int
    annotation_id: int
    true_label: str
    true_bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class Detection:
    label: str
    score: float
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class Prediction:
    split: str
    image_path: Path
    image_id: int
    annotation_id: int
    true_label: str
    predicted_label: str
    raw_predicted_label: str
    score: float
    iou: float
    true_bbox: tuple[float, float, float, float]
    predicted_bbox: Optional[tuple[float, float, float, float]]
    detections: tuple[Detection, ...]
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a MediaPipe ObjectDetector .tflite model on a COCO-style "
            "object dataset and save prediction ratios plus confusion matrices."
        )
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help=(
            "Dataset root or a split folder containing labels.json and images/. "
            f"Default: {DEFAULT_DATASET_DIR}"
        ),
    )
    parser.add_argument(
        "--split",
        choices=["train", "validation", "all"],
        default="all",
        help="Split to evaluate when --dataset is a dataset root. Default: all.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=(
            "Path to the object detector model. If no suffix is given, .tflite is tried. "
            f"Default: {DEFAULT_MODEL_PATH}"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for CSV and PNG outputs. Default: evaluation_results/<model>_on_<dataset>_<split>",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.3,
        help="Detection score threshold passed to MediaPipe ObjectDetector.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum detections returned by MediaPipe per image.",
    )
    parser.add_argument(
        "--iou-threshold",
        type=float,
        default=0.5,
        help="Minimum IoU for a prediction to count as a matched detection.",
    )
    parser.add_argument(
        "--confusion-mode",
        choices=["matched", "raw"],
        default="matched",
        help=(
            "matched: count low-IoU predictions as __LOW_IOU__. "
            "raw: use the best-IoU detection label even when IoU is low."
        ),
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use exact label strings when calculating accuracy and confusion matrices.",
    )
    parser.add_argument(
        "--copy-mistakes",
        action="store_true",
        help="Copy misclassified source images into output_dir/mistakes/<true>_as_<pred>/.",
    )
    parser.add_argument(
        "--draw-mistakes",
        action="store_true",
        help="Save annotated misclassified images with ground-truth and predicted boxes.",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip saving confusion matrix PNG files.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=50,
        help="Print progress every N images. Use 0 to disable progress output.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def resolve_model_path(model_path: Path) -> Path:
    model_path = resolve_path(model_path)
    if model_path.exists():
        return model_path
    if model_path.suffix == "":
        tflite_path = model_path.with_suffix(".tflite")
        if tflite_path.exists():
            return tflite_path
    return model_path


def default_output_dir(model_path: Path, dataset_dir: Path, split: str) -> Path:
    dataset_name = dataset_dir.name
    suffix = split if split != "all" else "all"
    return Path.cwd() / "evaluation_results" / f"{model_path.stem}_on_{dataset_name}_{suffix}"


def resolve_eval_folders(dataset_dir: Path, split: str) -> list[tuple[str, Path]]:
    if (dataset_dir / "labels.json").exists() and (dataset_dir / "images").exists():
        return [(dataset_dir.name, dataset_dir)]

    if split == "all":
        folders = []
        for split_name in ("train", "validation"):
            folder = dataset_dir / split_name
            if (folder / "labels.json").exists() and (folder / "images").exists():
                folders.append((split_name, folder))
        if folders:
            return folders
    else:
        folder = dataset_dir / split
        if (folder / "labels.json").exists() and (folder / "images").exists():
            return [(split, folder)]

    raise FileNotFoundError(
        f"Could not find labels.json and images/ under {dataset_dir} for split={split}."
    )


def load_ground_truths(eval_folders: Sequence[tuple[str, Path]]) -> list[GroundTruth]:
    ground_truths = []

    for split_name, folder in eval_folders:
        labels_path = folder / "labels.json"
        data = json.loads(labels_path.read_text(encoding="utf-8"))
        category_by_id = {category["id"]: category["name"] for category in data["categories"]}
        image_by_id = {image["id"]: image for image in data["images"]}

        for annotation in data["annotations"]:
            image = image_by_id.get(annotation["image_id"])
            if image is None:
                raise RuntimeError(
                    f"{labels_path}: annotation {annotation['id']} references missing image_id "
                    f"{annotation['image_id']}."
                )

            image_path = folder / "images" / image["file_name"]
            if not image_path.exists():
                raise FileNotFoundError(image_path)
            if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            label = category_by_id[annotation["category_id"]]
            ground_truths.append(
                GroundTruth(
                    split=split_name,
                    image_path=image_path,
                    image_id=int(image["id"]),
                    annotation_id=int(annotation["id"]),
                    true_label=label,
                    true_bbox=tuple(float(value) for value in annotation["bbox"]),
                )
            )

    return ground_truths


def create_detector(args: argparse.Namespace, model_path: Path) -> vision.ObjectDetector:
    options = vision.ObjectDetectorOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.IMAGE,
        score_threshold=args.score_threshold,
        max_results=args.max_results,
    )
    return vision.ObjectDetector.create_from_options(options)


def predict_ground_truth(
    detector: vision.ObjectDetector,
    ground_truth: GroundTruth,
    iou_threshold: float,
    confusion_mode: str,
) -> Prediction:
    try:
        result = detector.detect(mp.Image.create_from_file(str(ground_truth.image_path)))
    except Exception as exc:
        return Prediction(
            split=ground_truth.split,
            image_path=ground_truth.image_path,
            image_id=ground_truth.image_id,
            annotation_id=ground_truth.annotation_id,
            true_label=ground_truth.true_label,
            predicted_label=ERROR_LABEL,
            raw_predicted_label=ERROR_LABEL,
            score=0.0,
            iou=0.0,
            true_bbox=ground_truth.true_bbox,
            predicted_bbox=None,
            detections=(),
            error=str(exc),
        )

    detections = extract_detections(result)
    if not detections:
        return Prediction(
            split=ground_truth.split,
            image_path=ground_truth.image_path,
            image_id=ground_truth.image_id,
            annotation_id=ground_truth.annotation_id,
            true_label=ground_truth.true_label,
            predicted_label=NO_DETECTION_LABEL,
            raw_predicted_label=NO_DETECTION_LABEL,
            score=0.0,
            iou=0.0,
            true_bbox=ground_truth.true_bbox,
            predicted_bbox=None,
            detections=(),
        )

    best_detection = max(detections, key=lambda detection: bbox_iou(ground_truth.true_bbox, detection.bbox))
    best_iou = bbox_iou(ground_truth.true_bbox, best_detection.bbox)
    raw_predicted_label = best_detection.label

    if confusion_mode == "matched" and best_iou < iou_threshold:
        predicted_label = LOW_IOU_LABEL
    else:
        predicted_label = raw_predicted_label

    return Prediction(
        split=ground_truth.split,
        image_path=ground_truth.image_path,
        image_id=ground_truth.image_id,
        annotation_id=ground_truth.annotation_id,
        true_label=ground_truth.true_label,
        predicted_label=predicted_label,
        raw_predicted_label=raw_predicted_label,
        score=best_detection.score,
        iou=best_iou,
        true_bbox=ground_truth.true_bbox,
        predicted_bbox=best_detection.bbox,
        detections=tuple(detections),
    )


def extract_detections(result: vision.ObjectDetectorResult) -> list[Detection]:
    detections = []
    for detection in result.detections or []:
        if not detection.categories:
            continue

        category = detection.categories[0]
        bbox = detection.bounding_box
        detections.append(
            Detection(
                label=category_label(category),
                score=float(category.score),
                bbox=(
                    float(bbox.origin_x),
                    float(bbox.origin_y),
                    float(bbox.width),
                    float(bbox.height),
                ),
            )
        )

    return sorted(detections, key=lambda detection: detection.score, reverse=True)


def category_label(category) -> str:
    label = category.category_name or category.display_name
    if label:
        return str(label)
    return f"category_{category.index}"


def bbox_iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    first_x1, first_y1, first_w, first_h = first
    second_x1, second_y1, second_w, second_h = second
    first_x2 = first_x1 + first_w
    first_y2 = first_y1 + first_h
    second_x2 = second_x1 + second_w
    second_y2 = second_y1 + second_h

    inter_x1 = max(first_x1, second_x1)
    inter_y1 = max(first_y1, second_y1)
    inter_x2 = min(first_x2, second_x2)
    inter_y2 = min(first_y2, second_y2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    intersection = inter_w * inter_h

    first_area = max(0.0, first_w) * max(0.0, first_h)
    second_area = max(0.0, second_w) * max(0.0, second_h)
    union = first_area + second_area - intersection
    if union <= 0.0:
        return 0.0
    return intersection / union


def eval_label(label: str, case_sensitive: bool) -> str:
    label = label.strip()
    if label in SPECIAL_LABELS:
        return label
    if case_sensitive:
        return label
    return label.lower()


def is_correct(prediction: Prediction, case_sensitive: bool, iou_threshold: float) -> bool:
    return (
        prediction.iou >= iou_threshold
        and eval_label(prediction.true_label, case_sensitive)
        == eval_label(prediction.raw_predicted_label, case_sensitive)
    )


def build_label_orders(
    predictions: Iterable[Prediction],
    case_sensitive: bool,
) -> tuple[list[str], list[str]]:
    true_labels = []
    predicted_labels = []

    for prediction in predictions:
        true_labels.append(eval_label(prediction.true_label, case_sensitive))
        predicted_labels.append(eval_label(prediction.predicted_label, case_sensitive))

    row_labels = sorted(set(true_labels))
    column_extras = sorted(label for label in set(predicted_labels) if label not in row_labels)
    return row_labels, row_labels + column_extras


def build_confusion_matrix(
    predictions: Iterable[Prediction],
    row_labels: list[str],
    column_labels: list[str],
    case_sensitive: bool,
) -> np.ndarray:
    row_label_to_index = {label: index for index, label in enumerate(row_labels)}
    column_label_to_index = {label: index for index, label in enumerate(column_labels)}
    matrix = np.zeros((len(row_labels), len(column_labels)), dtype=int)

    for prediction in predictions:
        true_label = eval_label(prediction.true_label, case_sensitive)
        predicted_label = eval_label(prediction.predicted_label, case_sensitive)
        matrix[row_label_to_index[true_label], column_label_to_index[predicted_label]] += 1

    return matrix


def row_percent_matrix(matrix: np.ndarray) -> np.ndarray:
    row_sums = matrix.sum(axis=1, keepdims=True)
    return np.divide(
        matrix,
        row_sums,
        out=np.zeros_like(matrix, dtype=float),
        where=row_sums != 0,
    ) * 100.0


def write_predictions_csv(
    predictions: list[Prediction],
    output_path: Path,
    case_sensitive: bool,
    iou_threshold: float,
) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "split",
                "image_path",
                "true_label",
                "predicted_label",
                "raw_predicted_label",
                "score",
                "iou",
                "correct",
                "true_bbox_xywh",
                "predicted_bbox_xywh",
                "detections",
                "error",
            ]
        )
        for prediction in predictions:
            writer.writerow(
                [
                    prediction.split,
                    str(prediction.image_path),
                    prediction.true_label,
                    prediction.predicted_label,
                    prediction.raw_predicted_label,
                    f"{prediction.score:.6f}",
                    f"{prediction.iou:.6f}",
                    is_correct(prediction, case_sensitive, iou_threshold),
                    format_bbox(prediction.true_bbox),
                    format_bbox(prediction.predicted_bbox),
                    format_detections(prediction.detections),
                    prediction.error,
                ]
            )


def write_summary_csv(
    predictions: list[Prediction],
    output_path: Path,
    case_sensitive: bool,
) -> None:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for prediction in predictions:
        true_label = eval_label(prediction.true_label, case_sensitive)
        predicted_label = eval_label(prediction.predicted_label, case_sensitive)
        counters[true_label][predicted_label] += 1

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["true_label", "predicted_label", "count", "percent"])
        for true_label in sorted(counters):
            total = sum(counters[true_label].values())
            for predicted_label, count in counters[true_label].most_common():
                writer.writerow(
                    [true_label, predicted_label, count, f"{count / total * 100.0:.2f}"]
                )


def write_confusion_csv(
    matrix: np.ndarray,
    row_labels: list[str],
    column_labels: list[str],
    output_path: Path,
    percent: bool,
) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["true_label"] + column_labels)
        for label, row in zip(row_labels, matrix):
            if percent:
                writer.writerow([label] + [f"{value:.2f}" for value in row])
            else:
                writer.writerow([label] + [int(value) for value in row])


def write_metrics_json(
    predictions: list[Prediction],
    output_path: Path,
    args: argparse.Namespace,
    model_path: Path,
    eval_folders: Sequence[tuple[str, Path]],
) -> None:
    total = len(predictions)
    correct = sum(
        1
        for prediction in predictions
        if is_correct(prediction, args.case_sensitive, args.iou_threshold)
    )
    detected = sum(1 for prediction in predictions if prediction.predicted_label != NO_DETECTION_LABEL)
    matched_iou = sum(1 for prediction in predictions if prediction.iou >= args.iou_threshold)
    mean_iou = float(np.mean([prediction.iou for prediction in predictions])) if predictions else 0.0

    label_metrics = {}
    labels = sorted({eval_label(prediction.true_label, args.case_sensitive) for prediction in predictions})
    for label in labels:
        label_predictions = [
            prediction
            for prediction in predictions
            if eval_label(prediction.true_label, args.case_sensitive) == label
        ]
        label_total = len(label_predictions)
        label_correct = sum(
            1
            for prediction in label_predictions
            if is_correct(prediction, args.case_sensitive, args.iou_threshold)
        )
        label_metrics[label] = {
            "total": label_total,
            "correct": label_correct,
            "accuracy_percent": label_correct / label_total * 100.0 if label_total else 0.0,
            "mean_iou": float(np.mean([prediction.iou for prediction in label_predictions]))
            if label_predictions
            else 0.0,
        }

    output = {
        "model": str(model_path),
        "eval_folders": [{"split": split, "path": str(path)} for split, path in eval_folders],
        "score_threshold": args.score_threshold,
        "max_results": args.max_results,
        "iou_threshold": args.iou_threshold,
        "confusion_mode": args.confusion_mode,
        "total_ground_truths": total,
        "correct": correct,
        "accuracy_percent": correct / total * 100.0 if total else 0.0,
        "detected": detected,
        "detection_rate_percent": detected / total * 100.0 if total else 0.0,
        "matched_iou_count": matched_iou,
        "matched_iou_rate_percent": matched_iou / total * 100.0 if total else 0.0,
        "mean_iou": mean_iou,
        "label_metrics": label_metrics,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


def format_bbox(bbox: Optional[tuple[float, float, float, float]]) -> str:
    if bbox is None:
        return ""
    return ",".join(f"{value:.2f}" for value in bbox)


def format_detections(detections: Sequence[Detection]) -> str:
    return ";".join(
        f"{detection.label}:{detection.score:.6f}:{format_bbox(detection.bbox)}"
        for detection in detections
    )


def print_summary(
    predictions: list[Prediction],
    case_sensitive: bool,
    iou_threshold: float,
) -> None:
    total = len(predictions)
    correct = sum(1 for prediction in predictions if is_correct(prediction, case_sensitive, iou_threshold))
    accuracy = correct / total * 100.0 if total else 0.0
    no_detection = sum(1 for prediction in predictions if prediction.predicted_label == NO_DETECTION_LABEL)
    low_iou = sum(1 for prediction in predictions if prediction.predicted_label == LOW_IOU_LABEL)
    mean_iou = float(np.mean([prediction.iou for prediction in predictions])) if predictions else 0.0

    print()
    print(f"Total ground truths: {total}")
    print(f"Correct label with IoU >= {iou_threshold:.2f}: {correct}")
    print(f"Accuracy: {accuracy:.2f}%")
    print(f"No detection: {no_detection}")
    print(f"Low IoU: {low_iou}")
    print(f"Mean IoU: {mean_iou:.3f}")
    print()
    print("Prediction ratio by true label:")

    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for prediction in predictions:
        true_label = eval_label(prediction.true_label, case_sensitive)
        predicted_label = eval_label(prediction.predicted_label, case_sensitive)
        counters[true_label][predicted_label] += 1

    for true_label in sorted(counters):
        total_for_label = sum(counters[true_label].values())
        parts = [
            f"{predicted_label} {count / total_for_label * 100.0:.1f}% ({count})"
            for predicted_label, count in counters[true_label].most_common()
        ]
        print(f"- {true_label} (n={total_for_label}): " + ", ".join(parts))


def print_confusion_matrix(
    matrix: np.ndarray,
    row_labels: list[str],
    column_labels: list[str],
) -> None:
    all_labels = row_labels + column_labels
    label_width = max(12, min(20, max(len(label) for label in all_labels)))
    cell_width = max(8, min(12, label_width))

    print()
    print("Confusion matrix counts:")
    header = "true\\pred".ljust(label_width) + "".join(
        " " + trim(label, cell_width).rjust(cell_width) for label in column_labels
    )
    print(header)
    for label, row in zip(row_labels, matrix):
        values = "".join(" " + str(int(value)).rjust(cell_width) for value in row)
        print(trim(label, label_width).ljust(label_width) + values)


def trim(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "."


def save_confusion_plot(
    matrix: np.ndarray,
    row_labels: list[str],
    column_labels: list[str],
    output_path: Path,
    title: str,
    percent: bool,
) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
    except ImportError:
        print("[WARN] matplotlib is not installed; skipping PNG confusion matrix.")
        return False

    data = matrix.astype(float)
    figure_width = max(7.0, len(column_labels) * 1.15)
    figure_height = max(6.0, len(row_labels) * 1.0)
    fig, ax = plt.subplots(figsize=(figure_width, figure_height))
    image = ax.imshow(data, interpolation="nearest", cmap="Blues")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax.set_title(title)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_xticks(np.arange(len(column_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_xticklabels(column_labels, rotation=45, ha="right")
    ax.set_yticklabels(row_labels)

    threshold = data.max() / 2.0 if data.size and data.max() > 0 else 0.0
    for row_index in range(data.shape[0]):
        for col_index in range(data.shape[1]):
            value = data[row_index, col_index]
            text = f"{value:.1f}" if percent else str(int(value))
            color = "white" if value > threshold else "black"
            ax.text(col_index, row_index, text, ha="center", va="center", color=color, fontsize=9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return True


def copy_misclassified_images(
    predictions: list[Prediction],
    output_dir: Path,
    case_sensitive: bool,
    iou_threshold: float,
) -> None:
    mistakes_dir = output_dir / "mistakes"
    for prediction in predictions:
        if is_correct(prediction, case_sensitive, iou_threshold):
            continue

        true_label = eval_label(prediction.true_label, case_sensitive)
        predicted_label = eval_label(prediction.predicted_label, case_sensitive)
        target_dir = mistakes_dir / sanitize_filename(f"{true_label}_as_{predicted_label}")
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prediction.image_path, target_dir / prediction.image_path.name)


def draw_misclassified_images(
    predictions: list[Prediction],
    output_dir: Path,
    case_sensitive: bool,
    iou_threshold: float,
) -> None:
    annotated_dir = output_dir / "mistake_overlays"
    for prediction in predictions:
        if is_correct(prediction, case_sensitive, iou_threshold):
            continue

        image = cv2.imread(str(prediction.image_path))
        if image is None:
            continue

        draw_bbox(image, prediction.true_bbox, (0, 255, 0), f"GT {prediction.true_label}")
        if prediction.predicted_bbox is not None:
            draw_bbox(
                image,
                prediction.predicted_bbox,
                (0, 0, 255),
                f"PRED {prediction.raw_predicted_label} {prediction.score:.2f} IoU {prediction.iou:.2f}",
            )

        true_label = eval_label(prediction.true_label, case_sensitive)
        predicted_label = eval_label(prediction.predicted_label, case_sensitive)
        target_dir = annotated_dir / sanitize_filename(f"{true_label}_as_{predicted_label}")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / prediction.image_path.name
        cv2.imwrite(str(output_path), image)


def draw_bbox(
    image: np.ndarray,
    bbox: tuple[float, float, float, float],
    color: tuple[int, int, int],
    label: str,
) -> None:
    x, y, width, height = bbox
    x1 = max(0, int(round(x)))
    y1 = max(0, int(round(y)))
    x2 = min(image.shape[1] - 1, int(round(x + width)))
    y2 = min(image.shape[0] - 1, int(round(y + height)))

    cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)
    cv2.putText(
        image,
        label,
        (x1, max(20, y1 - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
        cv2.LINE_AA,
    )


def sanitize_filename(value: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    sanitized = "".join("_" if char in invalid_chars else char for char in value)
    return sanitized.strip().strip(".") or "unknown"


def main() -> None:
    args = parse_args()
    dataset_dir = resolve_path(args.dataset)
    model_path = resolve_model_path(args.model)
    output_dir = (
        resolve_path(args.output_dir)
        if args.output_dir
        else default_output_dir(model_path, dataset_dir, args.split)
    )

    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    eval_folders = resolve_eval_folders(dataset_dir, args.split)
    ground_truths = load_ground_truths(eval_folders)
    if not ground_truths:
        raise RuntimeError(f"No ground-truth annotations found under: {dataset_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Dataset: {dataset_dir}")
    print(f"Eval folders: {', '.join(f'{split}={folder}' for split, folder in eval_folders)}")
    print(f"Model: {model_path}")
    print(f"Output: {output_dir}")
    print(f"Ground truths: {len(ground_truths)}")

    predictions = []
    detector = create_detector(args, model_path)
    try:
        for index, ground_truth in enumerate(ground_truths, start=1):
            predictions.append(
                predict_ground_truth(
                    detector=detector,
                    ground_truth=ground_truth,
                    iou_threshold=args.iou_threshold,
                    confusion_mode=args.confusion_mode,
                )
            )
            if args.progress_every > 0 and index % args.progress_every == 0:
                print(f"Processed {index}/{len(ground_truths)} annotations...")
    finally:
        detector.close()

    mistakes = [
        prediction
        for prediction in predictions
        if not is_correct(prediction, args.case_sensitive, args.iou_threshold)
    ]
    row_labels, column_labels = build_label_orders(predictions, args.case_sensitive)
    counts_matrix = build_confusion_matrix(
        predictions,
        row_labels,
        column_labels,
        args.case_sensitive,
    )
    percent_matrix = row_percent_matrix(counts_matrix)

    predictions_csv = output_dir / "predictions.csv"
    mistakes_csv = output_dir / "misclassified.csv"
    summary_csv = output_dir / "prediction_ratio_by_true_label.csv"
    counts_csv = output_dir / "confusion_matrix_counts.csv"
    percent_csv = output_dir / "confusion_matrix_percent.csv"
    metrics_json = output_dir / "metrics.json"

    write_predictions_csv(predictions, predictions_csv, args.case_sensitive, args.iou_threshold)
    write_predictions_csv(mistakes, mistakes_csv, args.case_sensitive, args.iou_threshold)
    write_summary_csv(predictions, summary_csv, args.case_sensitive)
    write_confusion_csv(counts_matrix, row_labels, column_labels, counts_csv, percent=False)
    write_confusion_csv(percent_matrix, row_labels, column_labels, percent_csv, percent=True)
    write_metrics_json(predictions, metrics_json, args, model_path, eval_folders)

    if args.copy_mistakes:
        copy_misclassified_images(predictions, output_dir, args.case_sensitive, args.iou_threshold)
    if args.draw_mistakes:
        draw_misclassified_images(predictions, output_dir, args.case_sensitive, args.iou_threshold)

    if not args.no_plots:
        save_confusion_plot(
            counts_matrix,
            row_labels,
            column_labels,
            output_dir / "confusion_matrix_counts.png",
            "Object Detector Confusion Matrix (Counts)",
            percent=False,
        )
        save_confusion_plot(
            percent_matrix,
            row_labels,
            column_labels,
            output_dir / "confusion_matrix_percent.png",
            "Object Detector Confusion Matrix (Row %)",
            percent=True,
        )

    print_summary(predictions, args.case_sensitive, args.iou_threshold)
    print_confusion_matrix(counts_matrix, row_labels, column_labels)
    print()
    print("Saved files:")
    for path in [
        predictions_csv,
        mistakes_csv,
        summary_csv,
        counts_csv,
        percent_csv,
        metrics_json,
    ]:
        print(f"- {path}")
    if not args.no_plots:
        print(f"- {output_dir / 'confusion_matrix_counts.png'}")
        print(f"- {output_dir / 'confusion_matrix_percent.png'}")


if __name__ == "__main__":
    main()
