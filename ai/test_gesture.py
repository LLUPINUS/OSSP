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


DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "model" / "gesture_04.task"

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


@dataclass(frozen=True)
class HandResult:
    handedness: str
    gestures: tuple[tuple[str, float], ...]
    landmarks: tuple[object, ...]


@dataclass(frozen=True)
class FrameResult:
    timestamp_ms: int
    hands: tuple[HandResult, ...]


class LiveGestureRecognizer:
    def __init__(
        self,
        model_path: Path,
        num_hands: int,
        min_hand_detection_confidence: float,
        min_hand_presence_confidence: float,
        min_tracking_confidence: float,
        print_results: bool,
    ) -> None:
        self._lock = threading.Lock()
        self._latest_result: Optional[FrameResult] = None
        self._print_results = print_results

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

    def __enter__(self) -> "LiveGestureRecognizer":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def recognize_async(self, rgb_frame: np.ndarray, timestamp_ms: int) -> None:
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(rgb_frame),
        )
        self._recognizer.recognize_async(mp_image, timestamp_ms)

    def latest_result(self) -> Optional[FrameResult]:
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
            gestures = self._extract_gestures(result, hand_index)
            handedness = self._extract_handedness(result, hand_index)
            landmarks = self._extract_landmarks(result, hand_index)

            hands.append(
                HandResult(
                    handedness=handedness,
                    gestures=gestures,
                    landmarks=landmarks,
                )
            )

        frame_result = FrameResult(timestamp_ms=timestamp_ms, hands=tuple(hands))
        with self._lock:
            self._latest_result = frame_result

        if self._print_results:
            print(format_console_result(frame_result))

    @staticmethod
    def _extract_gestures(
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

    @staticmethod
    def _extract_handedness(
        result: vision.GestureRecognizerResult,
        hand_index: int,
    ) -> str:
        if not result.handedness or hand_index >= len(result.handedness):
            return "Unknown"
        if not result.handedness[hand_index]:
            return "Unknown"

        category = result.handedness[hand_index][0]
        return category.category_name or category.display_name or "Unknown"

    @staticmethod
    def _extract_landmarks(
        result: vision.GestureRecognizerResult,
        hand_index: int,
    ) -> tuple[object, ...]:
        if not result.hand_landmarks or hand_index >= len(result.hand_landmarks):
            return ()
        return tuple(result.hand_landmarks[hand_index])


def format_console_result(result: FrameResult) -> str:
    if not result.hands:
        return f"[{result.timestamp_ms}] no hand"

    summaries = []
    for hand in result.hands:
        if hand.gestures:
            label, score = hand.gestures[0]
            summaries.append(f"{hand.handedness}: {label} ({score:.3f})")
        else:
            summaries.append(f"{hand.handedness}: no gesture")
    return f"[{result.timestamp_ms}] " + " | ".join(summaries)


def resolve_model_path(model_path: Path) -> Path:
    if model_path.is_absolute():
        return model_path
    return (Path.cwd() / model_path).resolve()


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


def draw_hand_landmarks(
    frame: np.ndarray,
    hand: HandResult,
    hand_index: int,
) -> None:
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
        text = f"{label} {score:.2f}"
    else:
        text = "No gesture"

    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    draw_text_box(frame, text, (min_x, max(24, min_y - 10)), color)


def draw_text_box(
    frame: np.ndarray,
    text: str,
    origin: tuple[int, int],
    color: tuple[int, int, int],
    font_scale: float = 0.55,
) -> None:
    text = trim_text(text, 34)
    thickness = 2
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = origin
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


def draw_result_panel(
    frame: np.ndarray,
    result: Optional[FrameResult],
    fps: float,
    model_name: str,
    score_threshold: float,
    max_display_results: int,
) -> None:
    lines: list[tuple[str, tuple[int, int, int]]] = [
        (f"FPS: {fps:.1f}", (255, 255, 255)),
        (f"Model: {model_name}", (255, 255, 255)),
    ]

    if result is None:
        lines.append(("Waiting for callback result...", (0, 255, 255)))
    elif not result.hands:
        lines.append(("No hand detected", (0, 255, 255)))
    else:
        for hand_index, hand in enumerate(result.hands):
            if hand.gestures:
                label, score = hand.gestures[0]
                color = (0, 255, 0) if score >= score_threshold else (0, 180, 255)
                lines.append(
                    (
                        f"{hand_index + 1}. {hand.handedness}: {label} ({score:.3f})",
                        color,
                    )
                )
                for label, score in hand.gestures[1:max_display_results]:
                    lines.append((f"   {label} ({score:.3f})", (220, 220, 220)))
            else:
                lines.append((f"{hand_index + 1}. {hand.handedness}: no gesture", (0, 255, 255)))

    draw_panel_lines(frame, lines)


def draw_panel_lines(
    frame: np.ndarray,
    lines: Sequence[tuple[str, tuple[int, int, int]]],
) -> None:
    frame_height, frame_width = frame.shape[:2]
    panel_width = min(470, frame_width - 20)
    line_height = 28
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
            trim_text(text, 48),
            (22, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 0, 0),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            trim_text(text, 48),
            (22, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
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
        description="Test a custom MediaPipe Gesture Recognizer task model with webcam LIVE_STREAM input."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"Path to .task model. Default: {DEFAULT_MODEL_PATH}",
    )
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--width", type=int, default=640, help="Requested camera width.")
    parser.add_argument("--height", type=int, default=480, help="Requested camera height.")
    parser.add_argument("--num-hands", type=int, default=1, help="Maximum number of hands to detect.")
    parser.add_argument(
        "--send-fps",
        type=float,
        default=15.0,
        help="Maximum FPS sent to MediaPipe. The display can still refresh faster.",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.7,
        help="Score used only for coloring predictions on the display.",
    )
    parser.add_argument(
        "--max-display-results",
        type=int,
        default=3,
        help="Number of gesture categories to show for each detected hand.",
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
        "--print-results",
        action="store_true",
        help="Print top callback result to the terminal as well as drawing it.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_path = resolve_model_path(args.model)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index: {args.camera}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    send_interval_seconds = 1.0 / max(args.send_fps, 1.0)
    last_sent_seconds = 0.0
    last_timestamp_ms = -1
    last_frame_seconds = time.monotonic()
    fps = 0.0

    print(f"[INFO] Model: {model_path}")
    print("[INFO] Press ESC or q in the camera window to exit.")

    try:
        with LiveGestureRecognizer(
            model_path=model_path,
            num_hands=args.num_hands,
            min_hand_detection_confidence=args.min_hand_detection_confidence,
            min_hand_presence_confidence=args.min_hand_presence_confidence,
            min_tracking_confidence=args.min_tracking_confidence,
            print_results=args.print_results,
        ) as recognizer:
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
                    recognizer.recognize_async(rgb_frame, timestamp_ms)
                    last_timestamp_ms = timestamp_ms
                    last_sent_seconds = now_seconds

                latest = recognizer.latest_result()
                if latest is not None:
                    for hand_index, hand in enumerate(latest.hands):
                        draw_hand_landmarks(frame, hand, hand_index)

                draw_result_panel(
                    frame=frame,
                    result=latest,
                    fps=fps,
                    model_name=model_path.name,
                    score_threshold=args.score_threshold,
                    max_display_results=max(args.max_display_results, 1),
                )

                cv2.imshow("Custom Gesture Recognizer LIVE_STREAM", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
