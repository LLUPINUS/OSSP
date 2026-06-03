import argparse
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("GLOG_minloglevel", "2")

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


PROJECT_DIR = Path(__file__).resolve().parent
MODEL_DIR = PROJECT_DIR / "model"
DEFAULT_GESTURE_MODEL_PATH = (
    MODEL_DIR / "gesture_03.task"
)
DEFAULT_OBJECT_MODEL_PATH = (
    MODEL_DIR / "object_04.tflite"
)

HAND_CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (0, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (0, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (5, 9),
    (9, 13),
    (13, 17),
)

HAND_COLORS = (
    (0, 255, 0),
    (255, 180, 0),
    (0, 180, 255),
    (255, 0, 255),
)

OBJECT_COLORS = (
    (0, 180, 255),
    (255, 0, 180),
    (180, 255, 0),
    (255, 180, 0),
    (180, 0, 255),
)


@dataclass(frozen=True)
class HandResult:
    handedness: str
    gestures: tuple[tuple[str, float], ...]
    landmarks: tuple[object, ...]


@dataclass(frozen=True)
class GestureFrameResult:
    timestamp_ms: int
    hands: tuple[HandResult, ...]


@dataclass(frozen=True)
class ObjectDetection:
    label: str
    score: float
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class ObjectFrameResult:
    timestamp_ms: int
    detections: tuple[ObjectDetection, ...]


class LiveGestureRecognizer:
    def __init__(
        self,
        model_path: Path,
        num_hands: int,
        min_hand_detection_confidence: float,
        min_hand_presence_confidence: float,
        min_tracking_confidence: float,
    ) -> None:
        self._lock = threading.Lock()
        self._latest_result: Optional[GestureFrameResult] = None

        options = vision.GestureRecognizerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            result_callback=self._save_result,
        )
        self._recognizer = vision.GestureRecognizer.create_from_options(options)

    def close(self) -> None:
        self._recognizer.close()

    def recognize_async(self, mp_image: mp.Image, timestamp_ms: int) -> None:
        self._recognizer.recognize_async(mp_image, timestamp_ms)

    def latest_result(self) -> Optional[GestureFrameResult]:
        with self._lock:
            return self._latest_result

    def _save_result(
        self,
        result: vision.GestureRecognizerResult,
        output_image: mp.Image,
        timestamp_ms: int,
    ) -> None:
        hands = []
        hand_count = max(
            len(result.gestures or []),
            len(result.handedness or []),
            len(result.hand_landmarks or []),
        )

        for hand_index in range(hand_count):
            hands.append(
                HandResult(
                    handedness=extract_handedness(result, hand_index),
                    gestures=extract_gestures(result, hand_index),
                    landmarks=extract_landmarks(result, hand_index),
                )
            )

        with self._lock:
            self._latest_result = GestureFrameResult(timestamp_ms=timestamp_ms, hands=tuple(hands))


class LiveObjectDetector:
    def __init__(
        self,
        model_path: Path,
        score_threshold: float,
        max_results: int,
        category_allowlist: Optional[list[str]],
        category_denylist: Optional[list[str]],
    ) -> None:
        self._lock = threading.Lock()
        self._latest_result: Optional[ObjectFrameResult] = None

        options = vision.ObjectDetectorOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.LIVE_STREAM,
            score_threshold=score_threshold,
            max_results=max_results,
            category_allowlist=category_allowlist,
            category_denylist=category_denylist,
            result_callback=self._save_result,
        )
        self._detector = vision.ObjectDetector.create_from_options(options)

    def close(self) -> None:
        self._detector.close()

    def detect_async(self, mp_image: mp.Image, timestamp_ms: int) -> None:
        self._detector.detect_async(mp_image, timestamp_ms)

    def latest_result(self) -> Optional[ObjectFrameResult]:
        with self._lock:
            return self._latest_result

    def _save_result(
        self,
        result: vision.ObjectDetectorResult,
        output_image: mp.Image,
        timestamp_ms: int,
    ) -> None:
        detections = []
        for detection in result.detections or []:
            if not detection.categories:
                continue

            category = detection.categories[0]
            bbox = detection.bounding_box
            detections.append(
                ObjectDetection(
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

        detections.sort(key=lambda item: item.score, reverse=True)
        with self._lock:
            self._latest_result = ObjectFrameResult(
                timestamp_ms=timestamp_ms,
                detections=tuple(detections),
            )


def extract_gestures(
    result: vision.GestureRecognizerResult,
    hand_index: int,
) -> tuple[tuple[str, float], ...]:
    if not result.gestures or hand_index >= len(result.gestures):
        return ()

    gestures = []
    for category in result.gestures[hand_index]:
        label = category.category_name or category.display_name or str(category.index)
        gestures.append((label, float(category.score)))

    return tuple(sorted(gestures, key=lambda item: item[1], reverse=True))


def extract_handedness(result: vision.GestureRecognizerResult, hand_index: int) -> str:
    if not result.handedness or hand_index >= len(result.handedness):
        return "Unknown"
    if not result.handedness[hand_index]:
        return "Unknown"

    category = result.handedness[hand_index][0]
    return category.category_name or category.display_name or "Unknown"


def extract_landmarks(result: vision.GestureRecognizerResult, hand_index: int) -> tuple[object, ...]:
    if not result.hand_landmarks or hand_index >= len(result.hand_landmarks):
        return ()
    return tuple(result.hand_landmarks[hand_index])


def category_label(category) -> str:
    label = category.category_name or category.display_name
    if label:
        return str(label)
    return f"class_{category.index}"


def resolve_model_path(model_path: Path) -> Path:
    if model_path.is_absolute():
        resolved = model_path
    else:
        resolved = (Path.cwd() / model_path).resolve()

    if resolved.exists():
        return resolved

    if resolved.suffix == "":
        for suffix in (".task", ".tflite"):
            candidate = resolved.with_suffix(suffix)
            if candidate.exists():
                return candidate

    return resolved


def parse_csv_list(value: Optional[str]) -> Optional[list[str]]:
    if value is None or not value.strip():
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def gesture_signature(result: Optional[GestureFrameResult]) -> tuple:
    if result is None:
        return ("gesture_waiting",)
    if not result.hands:
        return ("no_gesture",)

    items = []
    for hand in result.hands:
        label = hand.gestures[0][0] if hand.gestures else "no_gesture"
        items.append((hand.handedness, label))
    return tuple(sorted(items))


def object_signature(result: Optional[ObjectFrameResult]) -> tuple:
    if result is None:
        return ("object_waiting",)
    if not result.detections:
        return ("no_object",)

    counts = {}
    for detection in result.detections:
        counts[detection.label] = counts.get(detection.label, 0) + 1
    return tuple(sorted(counts.items()))


def format_combined_result(
    gesture_result: Optional[GestureFrameResult],
    object_result: Optional[ObjectFrameResult],
) -> str:
    gesture_text = format_gesture_result(gesture_result)
    object_text = format_object_result(object_result)
    timestamp = max(
        gesture_result.timestamp_ms if gesture_result else -1,
        object_result.timestamp_ms if object_result else -1,
    )
    if timestamp >= 0:
        return f"[{timestamp}] Gesture: {gesture_text} | Object: {object_text}"
    return f"Gesture: {gesture_text} | Object: {object_text}"


def format_gesture_result(result: Optional[GestureFrameResult]) -> str:
    if result is None:
        return "waiting"
    if not result.hands:
        return "none"

    parts = []
    for hand in result.hands:
        if hand.gestures:
            label, score = hand.gestures[0]
            parts.append(f"{hand.handedness}:{label}({score:.2f})")
        else:
            parts.append(f"{hand.handedness}:none")
    return ", ".join(parts)


def format_object_result(result: Optional[ObjectFrameResult]) -> str:
    if result is None:
        return "waiting"
    if not result.detections:
        return "none"

    return ", ".join(
        f"{detection.label}({detection.score:.2f})"
        for detection in result.detections
    )


def landmark_points(
    landmarks: Sequence[object],
    frame_width: int,
    frame_height: int,
) -> list[tuple[int, int]]:
    points = []
    for landmark in landmarks:
        x = int(np.clip(landmark.x, 0.0, 1.0) * (frame_width - 1))
        y = int(np.clip(landmark.y, 0.0, 1.0) * (frame_height - 1))
        points.append((x, y))
    return points


def draw_hand_landmarks(frame: np.ndarray, hand: HandResult, hand_index: int) -> None:
    if not hand.landmarks:
        return

    frame_height, frame_width = frame.shape[:2]
    points = landmark_points(hand.landmarks, frame_width, frame_height)
    color = HAND_COLORS[hand_index % len(HAND_COLORS)]

    for start_index, end_index in HAND_CONNECTIONS:
        if start_index < len(points) and end_index < len(points):
            cv2.line(frame, points[start_index], points[end_index], color, 2)

    for point in points:
        cv2.circle(frame, point, 4, (0, 0, 255), -1)
        cv2.circle(frame, point, 5, (255, 255, 255), 1)

    if hand.gestures:
        label, score = hand.gestures[0]
        text = f"{hand.handedness} {label} {score:.2f}"
    else:
        text = f"{hand.handedness} no gesture"

    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    draw_text_box(frame, text, (min_x, max(24, min_y - 10)), color)


def draw_object_detections(frame: np.ndarray, result: Optional[ObjectFrameResult]) -> None:
    if result is None:
        return

    for index, detection in enumerate(result.detections):
        color = OBJECT_COLORS[index % len(OBJECT_COLORS)]
        x, y, width, height = detection.bbox
        x1 = max(0, int(round(x)))
        y1 = max(0, int(round(y)))
        x2 = min(frame.shape[1] - 1, int(round(x + width)))
        y2 = min(frame.shape[0] - 1, int(round(y + height)))

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        draw_text_box(
            frame,
            f"{detection.label} {detection.score:.2f}",
            (x1 + 4, max(24, y1 - 8)),
            color,
            font_scale=0.55,
        )


def draw_text_box(
    frame: np.ndarray,
    text: str,
    origin: tuple[int, int],
    color: tuple[int, int, int],
    font_scale: float = 0.55,
) -> None:
    text = trim_text(text, 40)
    thickness = 2
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = origin
    x = max(4, min(x, frame.shape[1] - text_size[0] - 12))
    y = max(y, text_size[1] + 8)

    cv2.rectangle(
        frame,
        (x - 4, y - text_size[1] - 8),
        (x + text_size[0] + 8, y + baseline + 4),
        (25, 25, 25),
        -1,
    )
    cv2.rectangle(
        frame,
        (x - 4, y - text_size[1] - 8),
        (x + text_size[0] + 8, y + baseline + 4),
        color,
        1,
    )
    cv2.putText(frame, text, (x, y), font, font_scale, (255, 255, 255), thickness)


def draw_status_panel(
    frame: np.ndarray,
    fps: float,
    gesture_result: Optional[GestureFrameResult],
    object_result: Optional[ObjectFrameResult],
    gesture_model_name: str,
    object_model_name: str,
) -> None:
    lines = [
        (f"FPS: {fps:.1f}", (255, 255, 255)),
        (f"Gesture model: {trim_text(gesture_model_name, 32)}", (255, 255, 255)),
        (f"Object model: {trim_text(object_model_name, 32)}", (255, 255, 255)),
        (f"Gesture: {trim_text(format_gesture_result(gesture_result), 50)}", (0, 255, 0)),
        (f"Object: {trim_text(format_object_result(object_result), 50)}", (0, 180, 255)),
    ]
    draw_panel_lines(frame, lines)


def draw_panel_lines(
    frame: np.ndarray,
    lines: Sequence[tuple[str, tuple[int, int, int]]],
) -> None:
    frame_height, frame_width = frame.shape[:2]
    panel_width = min(620, frame_width - 20)
    line_height = 27
    panel_height = min(frame_height - 20, 18 + line_height * len(lines))

    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (10 + panel_width, 10 + panel_height), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.62, frame, 0.38, 0, frame)

    y = 36
    for text, color in lines:
        if y > 10 + panel_height - 8:
            break
        cv2.putText(
            frame,
            trim_text(text, 70),
            (22, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (0, 0, 0),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            trim_text(text, 70),
            (22, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            color,
            2,
            cv2.LINE_AA,
        )
        y += line_height


def trim_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run custom MediaPipe gesture recognition and object detection together on webcam LIVE_STREAM input."
    )
    parser.add_argument(
        "--gesture-model",
        type=Path,
        default=DEFAULT_GESTURE_MODEL_PATH,
        help=f"Path to gesture .task model. Default: {DEFAULT_GESTURE_MODEL_PATH}",
    )
    parser.add_argument(
        "--object-model",
        type=Path,
        default=DEFAULT_OBJECT_MODEL_PATH,
        help=f"Path to object detector .tflite model. Default: {DEFAULT_OBJECT_MODEL_PATH}",
    )
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--width", type=int, default=1280, help="Requested camera width.")
    parser.add_argument("--height", type=int, default=720, help="Requested camera height.")
    parser.add_argument(
        "--send-fps",
        type=float,
        default=10.0,
        help="Maximum FPS sent to both MediaPipe tasks.",
    )
    parser.add_argument("--num-hands", type=int, default=2, help="Maximum hands to detect.")
    parser.add_argument(
        "--object-score-threshold",
        type=float,
        default=0.40,
        help="Object detector score threshold.",
    )
    parser.add_argument(
        "--object-max-results",
        type=int,
        default=5,
        help="Maximum object detections per frame.",
    )
    parser.add_argument(
        "--object-allowlist",
        type=str,
        default=None,
        help="Comma-separated object labels to allow, e.g. knife,tongs.",
    )
    parser.add_argument(
        "--object-denylist",
        type=str,
        default=None,
        help="Comma-separated object labels to deny.",
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
        "--flip",
        action="store_true",
        help="Horizontally flip the webcam frame for a mirror-like preview.",
    )
    parser.add_argument(
        "--print-score-change",
        action="store_true",
        help="Also print when rounded top scores change, not only labels/counts.",
    )
    return parser.parse_args()


def combined_signature(
    gesture_result: Optional[GestureFrameResult],
    object_result: Optional[ObjectFrameResult],
    include_scores: bool,
) -> tuple:
    if not include_scores:
        return (gesture_signature(gesture_result), object_signature(object_result))

    gesture_items = []
    if gesture_result is None:
        gesture_items.append(("waiting",))
    elif not gesture_result.hands:
        gesture_items.append(("none",))
    else:
        for hand in gesture_result.hands:
            if hand.gestures:
                label, score = hand.gestures[0]
                gesture_items.append((hand.handedness, label, round(score, 2)))
            else:
                gesture_items.append((hand.handedness, "none", 0.0))

    object_items = []
    if object_result is None:
        object_items.append(("waiting",))
    elif not object_result.detections:
        object_items.append(("none",))
    else:
        for detection in object_result.detections:
            object_items.append((detection.label, round(detection.score, 2)))

    return (tuple(sorted(gesture_items)), tuple(sorted(object_items)))


def main() -> None:
    args = parse_args()
    gesture_model_path = resolve_model_path(args.gesture_model)
    object_model_path = resolve_model_path(args.object_model)

    if not gesture_model_path.exists():
        raise FileNotFoundError(f"Gesture model file not found: {gesture_model_path}")
    if not object_model_path.exists():
        raise FileNotFoundError(f"Object model file not found: {object_model_path}")

    object_allowlist = parse_csv_list(args.object_allowlist)
    object_denylist = parse_csv_list(args.object_denylist)
    if object_allowlist and object_denylist:
        raise ValueError("--object-allowlist and --object-denylist cannot be used together.")

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index: {args.camera}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    gesture_recognizer = LiveGestureRecognizer(
        model_path=gesture_model_path,
        num_hands=args.num_hands,
        min_hand_detection_confidence=args.min_hand_detection_confidence,
        min_hand_presence_confidence=args.min_hand_presence_confidence,
        min_tracking_confidence=args.min_tracking_confidence,
    )
    object_detector = LiveObjectDetector(
        model_path=object_model_path,
        score_threshold=args.object_score_threshold,
        max_results=args.object_max_results,
        category_allowlist=object_allowlist,
        category_denylist=object_denylist,
    )

    send_interval_seconds = 1.0 / max(args.send_fps, 1.0)
    last_sent_seconds = 0.0
    last_timestamp_ms = -1
    last_frame_seconds = time.monotonic()
    fps = 0.0
    last_printed_signature = None

    print(f"[INFO] Gesture model: {gesture_model_path}")
    print(f"[INFO] Object model: {object_model_path}")
    print("[INFO] Press ESC or q in the camera window to exit.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("[WARN] Failed to read a frame from the camera.")
                break

            if args.flip:
                frame = cv2.flip(frame, 1)

            now_seconds = time.monotonic()
            frame_delta = now_seconds - last_frame_seconds
            last_frame_seconds = now_seconds
            if frame_delta > 0:
                current_fps = 1.0 / frame_delta
                fps = current_fps if fps == 0.0 else (0.9 * fps + 0.1 * current_fps)

            if now_seconds - last_sent_seconds >= send_interval_seconds:
                timestamp_ms = time.monotonic_ns() // 1_000_000
                if timestamp_ms <= last_timestamp_ms:
                    timestamp_ms = last_timestamp_ms + 1

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=np.ascontiguousarray(rgb_frame),
                )
                gesture_recognizer.recognize_async(mp_image, timestamp_ms)
                object_detector.detect_async(mp_image, timestamp_ms)

                last_timestamp_ms = timestamp_ms
                last_sent_seconds = now_seconds

            gesture_result = gesture_recognizer.latest_result()
            object_result = object_detector.latest_result()

            current_signature = combined_signature(
                gesture_result,
                object_result,
                include_scores=args.print_score_change,
            )
            if current_signature != last_printed_signature:
                print(format_combined_result(gesture_result, object_result))
                last_printed_signature = current_signature

            display_frame = frame.copy()
            draw_object_detections(display_frame, object_result)
            if gesture_result is not None:
                for hand_index, hand in enumerate(gesture_result.hands):
                    draw_hand_landmarks(display_frame, hand, hand_index)

            draw_status_panel(
                display_frame,
                fps=fps,
                gesture_result=gesture_result,
                object_result=object_result,
                gesture_model_name=gesture_model_path.name,
                object_model_name=object_model_path.name,
            )

            cv2.imshow("Gesture + Object LIVE_STREAM", display_frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break

    finally:
        gesture_recognizer.close()
        object_detector.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
