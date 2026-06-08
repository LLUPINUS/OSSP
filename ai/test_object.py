import sys
import time
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# =====================================================
# 사용자 설정: 여기만 수정해서 사용
# =====================================================

MODEL_PATH = Path(__file__).resolve().parent / "model" / "object_08.tflite"

CAMERA_ID = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

SCORE_THRESHOLD = 0.30
MAX_RESULTS = 5

MIRROR = True
PRINT_RESULTS = False

CATEGORY_ALLOWLIST = None
# 특정 클래스만 보고 싶으면 아래처럼 사용
# CATEGORY_ALLOWLIST = ["knife"]

CATEGORY_DENYLIST = None


# =====================================================
# 시각화 설정
# =====================================================

MARGIN = 10
ROW_SIZE = 20
FONT_SIZE = 1
FONT_THICKNESS = 1
BOX_THICKNESS = 3

# OpenCV는 BGR 색상 순서 사용
BOX_COLOR = (0, 255, 0)
TEXT_COLOR = (0, 0, 255)


# =====================================================
# 전역 상태값
# =====================================================

latest_detection_result = None
latest_result_timestamp_ms = -1


def get_category_text(category) -> str:
    category_name = getattr(category, "category_name", None)
    display_name = getattr(category, "display_name", None)
    index = getattr(category, "index", None)
    score = getattr(category, "score", 0.0)

    label = category_name or display_name or f"class_{index}"
    return f"{label} ({score:.2f})"


def visualize(image, detection_result):
    """
    detection_result를 OpenCV 이미지 위에 그림.
    image는 BGR 형식의 OpenCV frame.
    """

    if detection_result is None:
        return image

    for detection in detection_result.detections:
        bbox = detection.bounding_box

        x1 = max(0, int(bbox.origin_x))
        y1 = max(0, int(bbox.origin_y))
        x2 = min(image.shape[1] - 1, int(bbox.origin_x + bbox.width))
        y2 = min(image.shape[0] - 1, int(bbox.origin_y + bbox.height))

        cv2.rectangle(
            image,
            (x1, y1),
            (x2, y2),
            BOX_COLOR,
            BOX_THICKNESS,
        )

        if detection.categories:
            category = detection.categories[0]
            result_text = get_category_text(category)
        else:
            result_text = "unknown"

        text_location = (
            x1 + MARGIN,
            max(ROW_SIZE, y1 + MARGIN + ROW_SIZE),
        )

        cv2.putText(
            image,
            result_text,
            text_location,
            cv2.FONT_HERSHEY_PLAIN,
            FONT_SIZE,
            TEXT_COLOR,
            FONT_THICKNESS,
        )

    return image


def save_result(
    result: vision.ObjectDetectorResult,
    output_image: mp.Image,
    timestamp_ms: int,
):
    """
    LIVE_STREAM 모드에서 detect_async() 결과가 들어오는 callback 함수.
    """

    global latest_detection_result
    global latest_result_timestamp_ms

    latest_detection_result = result
    latest_result_timestamp_ms = timestamp_ms

    if PRINT_RESULTS:
        print(f"[{timestamp_ms} ms] detections: {len(result.detections)}")

        for detection in result.detections:
            bbox = detection.bounding_box

            if detection.categories:
                category = detection.categories[0]
                name = (
                    getattr(category, "category_name", None)
                    or getattr(category, "display_name", None)
                    or f"class_{getattr(category, 'index', None)}"
                )
                score = getattr(category, "score", 0.0)
            else:
                name = "unknown"
                score = 0.0

            print(
                f"  - {name}: {score:.3f}, "
                f"bbox=({bbox.origin_x}, {bbox.origin_y}, "
                f"{bbox.width}, {bbox.height})"
            )


def run():
    model_path = Path(MODEL_PATH)

    if not model_path.is_file():
        print(f"ERROR: Model file not found: {model_path}")
        sys.exit(1)

    if CATEGORY_ALLOWLIST and CATEGORY_DENYLIST:
        print("ERROR: CATEGORY_ALLOWLIST and CATEGORY_DENYLIST cannot be used together.")
        sys.exit(1)

    cap = cv2.VideoCapture(CAMERA_ID)

    if not cap.isOpened():
        print(f"ERROR: Unable to open webcam. CAMERA_ID = {CAMERA_ID}")
        print("Try changing CAMERA_ID to 1 or 2.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    base_options = python.BaseOptions(
        model_asset_path=str(model_path)
    )

    options = vision.ObjectDetectorOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.LIVE_STREAM,
        score_threshold=SCORE_THRESHOLD,
        max_results=MAX_RESULTS,
        category_allowlist=CATEGORY_ALLOWLIST,
        category_denylist=CATEGORY_DENYLIST,
        result_callback=save_result,
    )

    counter = 0
    fps = 0.0
    fps_avg_frame_count = 10
    fps_start_time = time.time()

    last_timestamp_ms = 0

    with vision.ObjectDetector.create_from_options(options) as detector:
        while cap.isOpened():
            success, frame = cap.read()

            if not success:
                print("ERROR: Unable to read from webcam.")
                break

            if MIRROR:
                frame = cv2.flip(frame, 1)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame,
            )

            timestamp_ms = time.monotonic_ns() // 1_000_000

            if timestamp_ms <= last_timestamp_ms:
                timestamp_ms = last_timestamp_ms + 1

            last_timestamp_ms = timestamp_ms

            detector.detect_async(mp_image, timestamp_ms)

            display_frame = frame.copy()

            if latest_detection_result is not None:
                display_frame = visualize(display_frame, latest_detection_result)
                detection_count = len(latest_detection_result.detections)
            else:
                detection_count = 0

            counter += 1

            if counter % fps_avg_frame_count == 0:
                now = time.time()
                fps = fps_avg_frame_count / (now - fps_start_time)
                fps_start_time = now

            cv2.putText(
                display_frame,
                f"FPS: {fps:.1f}",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )

            cv2.putText(
                display_frame,
                f"Detections: {detection_count}",
                (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )

            if latest_result_timestamp_ms >= 0:
                cv2.putText(
                    display_frame,
                    f"Timestamp: {latest_result_timestamp_ms} ms",
                    (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                )

            cv2.imshow(
                "MediaPipe Custom Object Detector",
                display_frame,
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == 27:
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()
