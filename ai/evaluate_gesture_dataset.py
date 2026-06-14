import argparse
import csv
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("GLOG_minloglevel", "2")

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.components.processors import ClassifierOptions


DEFAULT_DATASET_DIR = Path(__file__).resolve().parent / "gesture_dataset3"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "model" / "gesture_04.task"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

NO_HAND_LABEL = "__NO_HAND__"
NO_GESTURE_LABEL = "__NO_GESTURE__"
ERROR_LABEL = "__ERROR__"
SPECIAL_LABELS = {NO_HAND_LABEL, NO_GESTURE_LABEL, ERROR_LABEL}


@dataclass(frozen=True)
class Prediction:
    image_path: Path
    true_label: str
    predicted_label: str
    score: float
    top_predictions: str
    hands_detected: int
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a MediaPipe Gesture Recognizer .task model on a folder-per-class "
            "image dataset and save prediction ratios plus confusion matrices."
        )
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help=f"Dataset root. Each child folder is treated as a true class. Default: {DEFAULT_DATASET_DIR}",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"Path to the MediaPipe .task model. Default: {DEFAULT_MODEL_PATH}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for CSV and PNG outputs. Default: evaluation_results/<model>_on_<dataset>",
    )
    parser.add_argument("--num-hands", type=int, default=1, help="Maximum hands to detect per image.")
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Maximum gesture categories kept from each image for the CSV top_predictions column.",
    )
    parser.add_argument(
        "--classifier-score-threshold",
        type=float,
        default=0.0,
        help="Gesture classifier score threshold passed to MediaPipe. Default keeps all returned results.",
    )
    parser.add_argument(
        "--min-hand-detection-confidence",
        type=float,
        default=0.5,
        help="Minimum confidence for initial hand detection.",
    )
    parser.add_argument(
        "--min-hand-presence-confidence",
        type=float,
        default=0.5,
        help="Minimum confidence for hand presence in landmark detection.",
    )
    parser.add_argument(
        "--min-tracking-confidence",
        type=float,
        default=0.5,
        help="Minimum confidence for hand tracking.",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use exact label strings when calculating accuracy and confusion matrices.",
    )
    parser.add_argument(
        "--max-images-per-class",
        type=int,
        default=0,
        help="Limit images per class for a quick test. 0 means use all images.",
    )
    parser.add_argument(
        "--copy-mistakes",
        action="store_true",
        help="Copy misclassified images into output_dir/mistakes/<true>_as_<pred>/.",
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
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def default_output_dir(model_path: Path, dataset_dir: Path) -> Path:
    return Path.cwd() / "evaluation_results" / f"{model_path.stem}_on_{dataset_dir.name}"


def iter_dataset_images(
    dataset_dir: Path,
    max_images_per_class: int,
) -> list[tuple[Path, str]]:
    samples = []
    class_dirs = [path for path in sorted(dataset_dir.iterdir()) if path.is_dir()]

    for class_dir in class_dirs:
        image_paths = sorted(
            path
            for path in class_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if max_images_per_class > 0:
            image_paths = image_paths[:max_images_per_class]
        samples.extend((image_path, class_dir.name) for image_path in image_paths)

    return samples


def create_recognizer(args: argparse.Namespace, model_path: Path) -> vision.GestureRecognizer:
    classifier_options = ClassifierOptions(
        max_results=max(args.top_k, 1),
        score_threshold=args.classifier_score_threshold,
    )
    options = vision.GestureRecognizerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.IMAGE,
        num_hands=args.num_hands,
        min_hand_detection_confidence=args.min_hand_detection_confidence,
        min_hand_presence_confidence=args.min_hand_presence_confidence,
        min_tracking_confidence=args.min_tracking_confidence,
        canned_gesture_classifier_options=classifier_options,
        custom_gesture_classifier_options=classifier_options,
    )
    return vision.GestureRecognizer.create_from_options(options)


def predict_image(
    recognizer: vision.GestureRecognizer,
    image_path: Path,
    true_label: str,
) -> Prediction:
    try:
        result = recognizer.recognize(mp.Image.create_from_file(str(image_path)))
    except Exception as exc:
        return Prediction(
            image_path=image_path,
            true_label=true_label,
            predicted_label=ERROR_LABEL,
            score=0.0,
            top_predictions="",
            hands_detected=0,
            error=str(exc),
        )

    hands_detected = len(result.hand_landmarks or [])
    candidates = []
    top_prediction_parts = []

    for hand_index, categories in enumerate(result.gestures or []):
        sorted_categories = sorted(categories, key=lambda category: category.score, reverse=True)
        for category in sorted_categories:
            label = category_label(category)
            score = float(category.score)
            candidates.append((label, score, hand_index))
            top_prediction_parts.append(f"hand{hand_index}:{label}:{score:.6f}")

    if candidates:
        predicted_label, score, _ = max(candidates, key=lambda item: item[1])
    elif hands_detected > 0:
        predicted_label = NO_GESTURE_LABEL
        score = 0.0
    else:
        predicted_label = NO_HAND_LABEL
        score = 0.0

    return Prediction(
        image_path=image_path,
        true_label=true_label,
        predicted_label=predicted_label,
        score=score,
        top_predictions=";".join(top_prediction_parts),
        hands_detected=hands_detected,
    )


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
        prediction.predicted_label, case_sensitive
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
    column_labels = row_labels + column_extras
    return row_labels, column_labels


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
                "image_path",
                "true_label",
                "predicted_label",
                "score",
                "correct",
                "hands_detected",
                "top_predictions",
                "error",
            ]
        )
        for prediction in predictions:
            writer.writerow(
                [
                    str(prediction.image_path),
                    prediction.true_label,
                    prediction.predicted_label,
                    f"{prediction.score:.6f}",
                    is_correct(prediction, case_sensitive),
                    prediction.hands_detected,
                    prediction.top_predictions,
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


def print_summary(predictions: list[Prediction], case_sensitive: bool) -> None:
    total = len(predictions)
    correct = sum(1 for prediction in predictions if is_correct(prediction, case_sensitive))
    accuracy = correct / total * 100.0 if total else 0.0

    print()
    print(f"Total images: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {accuracy:.2f}%")
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
            if percent:
                text = f"{value:.1f}"
            else:
                text = str(int(value))
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


def sanitize_filename(value: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    sanitized = "".join("_" if char in invalid_chars else char for char in value)
    return sanitized.strip().strip(".") or "unknown"


def main() -> None:
    args = parse_args()
    dataset_dir = resolve_path(args.dataset)
    model_path = resolve_path(args.model)
    output_dir = resolve_path(args.output_dir) if args.output_dir else default_output_dir(model_path, dataset_dir)

    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    samples = iter_dataset_images(dataset_dir, args.max_images_per_class)
    if not samples:
        raise RuntimeError(f"No image files found under: {dataset_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Dataset: {dataset_dir}")
    print(f"Model: {model_path}")
    print(f"Output: {output_dir}")
    print(f"Images: {len(samples)}")

    predictions = []
    recognizer = create_recognizer(args, model_path)
    try:
        for index, (image_path, true_label) in enumerate(samples, start=1):
            predictions.append(predict_image(recognizer, image_path, true_label))
            if args.progress_every > 0 and index % args.progress_every == 0:
                print(f"Processed {index}/{len(samples)} images...")
    finally:
        recognizer.close()

    row_labels, column_labels = build_label_orders(predictions, args.case_sensitive)
    counts_matrix = build_confusion_matrix(
        predictions,
        row_labels,
        column_labels,
        args.case_sensitive,
    )
    percent_matrix = row_percent_matrix(counts_matrix)
    mistakes = [
        prediction
        for prediction in predictions
        if not is_correct(prediction, args.case_sensitive)
    ]

    predictions_csv = output_dir / "predictions.csv"
    mistakes_csv = output_dir / "misclassified.csv"
    summary_csv = output_dir / "prediction_ratio_by_true_label.csv"
    counts_csv = output_dir / "confusion_matrix_counts.csv"
    percent_csv = output_dir / "confusion_matrix_percent.csv"

    write_predictions_csv(predictions, predictions_csv, args.case_sensitive)
    write_predictions_csv(mistakes, mistakes_csv, args.case_sensitive)
    write_summary_csv(predictions, summary_csv, args.case_sensitive)
    write_confusion_csv(counts_matrix, row_labels, column_labels, counts_csv, percent=False)
    write_confusion_csv(percent_matrix, row_labels, column_labels, percent_csv, percent=True)

    if args.copy_mistakes:
        copy_misclassified_images(predictions, output_dir, args.case_sensitive)

    if not args.no_plots:
        save_confusion_plot(
            counts_matrix,
            row_labels,
            column_labels,
            output_dir / "confusion_matrix_counts.png",
            "Confusion Matrix (Counts)",
            percent=False,
        )
        save_confusion_plot(
            percent_matrix,
            row_labels,
            column_labels,
            output_dir / "confusion_matrix_percent.png",
            "Confusion Matrix (Row %)",
            percent=True,
        )

    print_summary(predictions, args.case_sensitive)
    print_confusion_matrix(counts_matrix, row_labels, column_labels)
    print()
    print("Saved files:")
    for path in [predictions_csv, mistakes_csv, summary_csv, counts_csv, percent_csv]:
        print(f"- {path}")
    if not args.no_plots:
        print(f"- {output_dir / 'confusion_matrix_counts.png'}")
        print(f"- {output_dir / 'confusion_matrix_percent.png'}")


if __name__ == "__main__":
    main()
