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


DEFAULT_DATASET_DIR = Path(__file__).resolve().parent / "gesture_dataset2"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "model" / "object_04.tflite"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

NO_DETECTION_LABEL = "__NO_DETECTION__"
ERROR_LABEL = "__ERROR__"
SPECIAL_LABELS = {NO_DETECTION_LABEL, ERROR_LABEL}

# Long/specific aliases must come before short generic aliases.
DEFAULT_LABEL_ALIASES: tuple[tuple[str, str], ...] = (
    ("woodenspoon", "spoon"),
    ("wood_spoon", "spoon"),
    ("woodspoon", "spoon"),
    ("tablespoon", "spoon"),
    ("kitchenknife", "knife"),
    ("kitchen_knife", "knife"),
    ("fishslice", "spatula"),
    ("fish_slice", "spatula"),
    ("turner", "spatula"),
    ("spatula", "spatula"),
    ("ladle", "ladle"),
    ("tongs", "tongs"),
    ("knife", "knife"),
    ("spoon", "spoon"),
)


@dataclass(frozen=True)
class ImageSample:
    split: str
    image_path: Path
    image_id: int
    true_label: str
    matched_alias: str


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
    true_label: str
    predicted_label: str
    raw_predicted_label: str
    score: float
    predicted_bbox: Optional[tuple[float, float, float, float]]
    detections: tuple[Detection, ...]
    matched_alias: str
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a MediaPipe ObjectDetector .tflite model on recursively found "
            "images whose filenames contain the true object label. No labels.json or "
            "ground-truth bbox is required, so correctness is label-only."
        )
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help=f"Root folder containing images in any nested structure. Default: {DEFAULT_DATASET_DIR}",
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
        help="Directory for CSV and PNG outputs. Default: evaluation_results/<model>_filename_labels_on_<dataset>",
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
        "--case-sensitive",
        action="store_true",
        help="Use exact label strings when calculating accuracy and confusion matrices.",
    )
    parser.add_argument(
        "--match-any-detection",
        action="store_true",
        help=(
            "Count an image as correct when any returned detection has the true label. "
            "By default only the highest-score detection is used for confusion matrices and accuracy."
        ),
    )
    parser.add_argument(
        "--aliases",
        type=str,
        default=None,
        help=(
            "Optional comma-separated filename aliases, e.g. "
            "'knife=knife,kitchenknife=knife,turner=spatula'. Defaults cover the current datasets."
        ),
    )
    parser.add_argument(
        "--copy-mistakes",
        action="store_true",
        help="Copy misclassified source images into output_dir/mistakes/<true>_as_<pred>/.",
    )
    parser.add_argument(
        "--draw-mistakes",
        action="store_true",
        help="Save misclassified images with predicted bboxes drawn.",
    )
    parser.add_argument(
        "--draw-predictions",
        action="store_true",
        help="Save all images with predicted bboxes drawn.",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip saving confusion matrix PNG files.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print progress every N images. Use 0 to disable progress output.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Evaluate only the first N labeled images. Useful for a quick smoke test.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def resolve_model_path(model_path: Path) -> Path:
    model_path = resolve_path(model_path)
    if model_path.suffix == "":
        tflite_path = model_path.with_suffix(".tflite")
        if tflite_path.exists():
            return tflite_path
    if model_path.exists():
        return model_path
    return model_path


def default_output_dir(model_path: Path, dataset_dir: Path) -> Path:
    return (
        Path.cwd()
        / "evaluation_results"
        / f"{model_path.stem}_filename_labels_on_{dataset_dir.name}"
    )


def parse_aliases(value: Optional[str]) -> tuple[tuple[str, str], ...]:
    if value is None:
        return DEFAULT_LABEL_ALIASES

    aliases = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Invalid alias entry '{item}'. Expected alias=label.")
        alias, label = item.split("=", 1)
        aliases.append((normalize_filename_text(alias), label.strip().lower()))

    return tuple(sorted(aliases, key=lambda pair: len(pair[0]), reverse=True))


def normalize_filename_text(value: str) -> str:
    return (
        value.lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace(".", "_")
    )


def infer_label_from_filename(
    image_path: Path,
    aliases: Sequence[tuple[str, str]],
) -> tuple[Optional[str], str]:
    normalized_name = normalize_filename_text(image_path.stem)
    for alias, label in aliases:
        if normalize_filename_text(alias) in normalized_name:
            return label, alias
    return None, ""


def infer_split(dataset_dir: Path, image_path: Path) -> str:
    try:
        relative_parts = image_path.relative_to(dataset_dir).parts
    except ValueError:
        return image_path.parent.name

    for part in relative_parts[:-1]:
        normalized = part.lower()
        if normalized in {"train", "training"}:
            return "train"
        if normalized in {"validation", "valid", "val"}:
            return "validation"
        if normalized in {"test", "testing"}:
            return "test"

    if len(relative_parts) > 1:
        return str(Path(*relative_parts[:-1]))
    return dataset_dir.name


def collect_image_samples(
    dataset_dir: Path,
    aliases: Sequence[tuple[str, str]],
    limit: int,
) -> tuple[list[ImageSample], list[Path]]:
    samples = []
    unlabeled = []

    image_paths = sorted(
        path
        for path in dataset_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    for image_path in image_paths:
        label, matched_alias = infer_label_from_filename(image_path, aliases)
        if label is None:
            unlabeled.append(image_path)
            continue

        samples.append(
            ImageSample(
                split=infer_split(dataset_dir, image_path),
                image_path=image_path,
                image_id=len(samples),
                true_label=label,
                matched_alias=matched_alias,
            )
        )
        if limit > 0 and len(samples) >= limit:
            break

    return samples, unlabeled


def create_detector(args: argparse.Namespace, model_path: Path) -> vision.ObjectDetector:
    options = vision.ObjectDetectorOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.IMAGE,
        score_threshold=args.score_threshold,
        max_results=args.max_results,
    )
    return vision.ObjectDetector.create_from_options(options)


def predict_sample(
    detector: vision.ObjectDetector,
    sample: ImageSample,
    case_sensitive: bool,
    match_any_detection: bool,
) -> Prediction:
    try:
        result = detector.detect(mp.Image.create_from_file(str(sample.image_path)))
    except Exception as exc:
        return Prediction(
            split=sample.split,
            image_path=sample.image_path,
            image_id=sample.image_id,
            true_label=sample.true_label,
            predicted_label=ERROR_LABEL,
            raw_predicted_label=ERROR_LABEL,
            score=0.0,
            predicted_bbox=None,
            detections=(),
            matched_alias=sample.matched_alias,
            error=str(exc),
        )

    detections = extract_detections(result)
    if not detections:
        return Prediction(
            split=sample.split,
            image_path=sample.image_path,
            image_id=sample.image_id,
            true_label=sample.true_label,
            predicted_label=NO_DETECTION_LABEL,
            raw_predicted_label=NO_DETECTION_LABEL,
            score=0.0,
            predicted_bbox=None,
            detections=(),
            matched_alias=sample.matched_alias,
        )

    top_detection = detections[0]
    predicted_label = top_detection.label
    if match_any_detection:
        true_label = eval_label(sample.true_label, case_sensitive)
        matching_detection = next(
            (
                detection
                for detection in detections
                if eval_label(detection.label, case_sensitive) == true_label
            ),
            None,
        )
        if matching_detection is not None:
            predicted_label = matching_detection.label

    return Prediction(
        split=sample.split,
        image_path=sample.image_path,
        image_id=sample.image_id,
        true_label=sample.true_label,
        predicted_label=predicted_label,
        raw_predicted_label=top_detection.label,
        score=top_detection.score,
        predicted_bbox=top_detection.bbox,
        detections=tuple(detections),
        matched_alias=sample.matched_alias,
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


def eval_label(label: str, case_sensitive: bool) -> str:
    label = label.strip()
    if label in SPECIAL_LABELS:
        return label
    if case_sensitive:
        return label
    return label.lower()


def is_correct(prediction: Prediction, case_sensitive: bool) -> bool:
    return eval_label(prediction.true_label, case_sensitive) == eval_label(
        prediction.predicted_label,
        case_sensitive,
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
) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "split",
                "image_path",
                "file_name",
                "matched_alias",
                "true_label",
                "predicted_label",
                "raw_top_predicted_label",
                "score",
                "correct",
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
                    prediction.image_path.name,
                    prediction.matched_alias,
                    prediction.true_label,
                    prediction.predicted_label,
                    prediction.raw_predicted_label,
                    f"{prediction.score:.6f}",
                    is_correct(prediction, case_sensitive),
                    format_bbox(prediction.predicted_bbox),
                    format_detections(prediction.detections),
                    prediction.error,
                ]
            )


def write_unlabeled_csv(paths: Sequence[Path], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["image_path", "file_name"])
        for path in paths:
            writer.writerow([str(path), path.name])


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
                writer.writerow([true_label, predicted_label, count, f"{count / total * 100.0:.2f}"])


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
    dataset_dir: Path,
    unlabeled_count: int,
    aliases: Sequence[tuple[str, str]],
) -> None:
    total = len(predictions)
    correct = sum(1 for prediction in predictions if is_correct(prediction, args.case_sensitive))
    detected = sum(1 for prediction in predictions if prediction.predicted_label != NO_DETECTION_LABEL)
    error_count = sum(1 for prediction in predictions if prediction.predicted_label == ERROR_LABEL)

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
            1 for prediction in label_predictions if is_correct(prediction, args.case_sensitive)
        )
        label_metrics[label] = {
            "total": label_total,
            "correct": label_correct,
            "accuracy_percent": label_correct / label_total * 100.0 if label_total else 0.0,
        }

    output = {
        "mode": "filename_label_only",
        "note": "No ground-truth bbox is available, so IoU and localization accuracy are not calculated.",
        "dataset": str(dataset_dir),
        "model": str(model_path),
        "score_threshold": args.score_threshold,
        "max_results": args.max_results,
        "match_any_detection": args.match_any_detection,
        "aliases": [{"alias": alias, "label": label} for alias, label in aliases],
        "total_labeled_images": total,
        "unlabeled_images_skipped": unlabeled_count,
        "correct": correct,
        "accuracy_percent": correct / total * 100.0 if total else 0.0,
        "detected": detected,
        "detection_rate_percent": detected / total * 100.0 if total else 0.0,
        "errors": error_count,
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


def print_summary(predictions: list[Prediction], case_sensitive: bool, unlabeled_count: int) -> None:
    total = len(predictions)
    correct = sum(1 for prediction in predictions if is_correct(prediction, case_sensitive))
    accuracy = correct / total * 100.0 if total else 0.0
    no_detection = sum(1 for prediction in predictions if prediction.predicted_label == NO_DETECTION_LABEL)
    error_count = sum(1 for prediction in predictions if prediction.predicted_label == ERROR_LABEL)

    print()
    print(f"Total labeled images: {total}")
    print(f"Correct filename-label predictions: {correct}")
    print(f"Accuracy: {accuracy:.2f}%")
    print(f"No detection: {no_detection}")
    print(f"Errors: {error_count}")
    print(f"Unlabeled images skipped: {unlabeled_count}")
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

    figure_width = max(7.0, len(column_labels) * 1.15)
    figure_height = max(6.0, len(row_labels) * 1.0)
    fig, ax = plt.subplots(figsize=(figure_width, figure_height))
    image = ax.imshow(matrix, interpolation="nearest", cmap="Blues")
    ax.figure.colorbar(image, ax=ax)
    ax.set_title(title)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_xticks(np.arange(len(column_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_xticklabels(column_labels, rotation=45, ha="right")
    ax.set_yticklabels(row_labels)

    threshold = matrix.max() / 2.0 if matrix.size else 0.0
    for row_index in range(matrix.shape[0]):
        for column_index in range(matrix.shape[1]):
            value = matrix[row_index, column_index]
            text = f"{value:.1f}" if percent else str(int(value))
            ax.text(
                column_index,
                row_index,
                text,
                ha="center",
                va="center",
                color="white" if value > threshold else "black",
                fontsize=9,
            )

    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return True


def sanitize_filename(value: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    sanitized = "".join("_" if char in invalid_chars else char for char in value)
    return sanitized.strip().strip(".") or "unknown"


def copy_misclassified_images(
    predictions: list[Prediction],
    output_dir: Path,
    case_sensitive: bool,
) -> None:
    mistakes_dir = output_dir / "mistakes"
    for prediction in predictions:
        if is_correct(prediction, case_sensitive):
            continue

        true_label = eval_label(prediction.true_label, case_sensitive)
        predicted_label = eval_label(prediction.predicted_label, case_sensitive)
        target_dir = mistakes_dir / sanitize_filename(f"{true_label}_as_{predicted_label}")
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prediction.image_path, target_dir / prediction.image_path.name)


def draw_prediction_images(
    predictions: list[Prediction],
    output_dir: Path,
    case_sensitive: bool,
    mistakes_only: bool,
) -> None:
    target_root = output_dir / ("mistake_overlays" if mistakes_only else "prediction_overlays")
    for prediction in predictions:
        if mistakes_only and is_correct(prediction, case_sensitive):
            continue

        image = cv2.imread(str(prediction.image_path))
        if image is None:
            continue

        for index, detection in enumerate(prediction.detections):
            color = (0, 0, 255) if index == 0 else (255, 128, 0)
            draw_bbox(image, detection.bbox, color, f"{detection.label} {detection.score:.2f}")

        folder = (
            sanitize_filename(
                f"{eval_label(prediction.true_label, case_sensitive)}_as_"
                f"{eval_label(prediction.predicted_label, case_sensitive)}"
            )
            if mistakes_only
            else sanitize_filename(eval_label(prediction.true_label, case_sensitive))
        )
        target_dir = target_root / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(target_dir / prediction.image_path.name), image)


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


def main() -> None:
    args = parse_args()
    dataset_dir = resolve_path(args.dataset)
    model_path = resolve_model_path(args.model)
    output_dir = (
        resolve_path(args.output_dir)
        if args.output_dir
        else default_output_dir(model_path, dataset_dir)
    )
    aliases = parse_aliases(args.aliases)

    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    samples, unlabeled = collect_image_samples(dataset_dir, aliases, args.limit)
    if not samples:
        raise RuntimeError(f"No labeled images found by filename under: {dataset_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Dataset: {dataset_dir}")
    print(f"Model: {model_path}")
    print(f"Output: {output_dir}")
    print(f"Labeled images: {len(samples)}")
    print(f"Unlabeled images skipped: {len(unlabeled)}")
    print("Label counts:", dict(Counter(sample.true_label for sample in samples)))

    predictions = []
    detector = create_detector(args, model_path)
    try:
        for index, sample in enumerate(samples, start=1):
            predictions.append(
                predict_sample(
                    detector=detector,
                    sample=sample,
                    case_sensitive=args.case_sensitive,
                    match_any_detection=args.match_any_detection,
                )
            )
            if args.progress_every > 0 and index % args.progress_every == 0:
                print(f"Processed {index}/{len(samples)} images...")
    finally:
        detector.close()

    mistakes = [
        prediction
        for prediction in predictions
        if not is_correct(prediction, args.case_sensitive)
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
    unlabeled_csv = output_dir / "unlabeled_images.csv"

    write_predictions_csv(predictions, predictions_csv, args.case_sensitive)
    write_predictions_csv(mistakes, mistakes_csv, args.case_sensitive)
    write_summary_csv(predictions, summary_csv, args.case_sensitive)
    write_confusion_csv(counts_matrix, row_labels, column_labels, counts_csv, percent=False)
    write_confusion_csv(percent_matrix, row_labels, column_labels, percent_csv, percent=True)
    write_unlabeled_csv(unlabeled, unlabeled_csv)
    write_metrics_json(
        predictions=predictions,
        output_path=metrics_json,
        args=args,
        model_path=model_path,
        dataset_dir=dataset_dir,
        unlabeled_count=len(unlabeled),
        aliases=aliases,
    )

    if args.copy_mistakes:
        copy_misclassified_images(predictions, output_dir, args.case_sensitive)
    if args.draw_mistakes:
        draw_prediction_images(predictions, output_dir, args.case_sensitive, mistakes_only=True)
    if args.draw_predictions:
        draw_prediction_images(predictions, output_dir, args.case_sensitive, mistakes_only=False)

    if not args.no_plots:
        save_confusion_plot(
            counts_matrix,
            row_labels,
            column_labels,
            output_dir / "confusion_matrix_counts.png",
            "Filename-Label Object Confusion Matrix (Counts)",
            percent=False,
        )
        save_confusion_plot(
            percent_matrix,
            row_labels,
            column_labels,
            output_dir / "confusion_matrix_percent.png",
            "Filename-Label Object Confusion Matrix (Row %)",
            percent=True,
        )

    print_summary(predictions, args.case_sensitive, len(unlabeled))
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
        unlabeled_csv,
    ]:
        print(f"- {path}")
    if not args.no_plots:
        print(f"- {output_dir / 'confusion_matrix_counts.png'}")
        print(f"- {output_dir / 'confusion_matrix_percent.png'}")


if __name__ == "__main__":
    main()
