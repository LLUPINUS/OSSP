# AI / CV Recognition

MediaPipe Tasks API 기반의 커스텀 gesture recognizer와 object detector를 사용해
카메라 라이브스트림에서 손동작과 조리도구를 감지하는 AI/CV 모듈입니다.

## Models

- Gesture recognizer: `model/gesture_03.task`
- Object detector: `model/object_08.tflite`

## Classes

Gesture classes:

- `index_grip`
- `light_grip`
- `pen_grip`
- `tongs`
- `none`

Object classes:

- `knife`
- `ladle`
- `spatula`
- `spoon`
- `tongs`

## Setup

```bash
pip install -r ai/requirements.txt
```

## Live Inference

Gesture + object 동시 감지:

```bash
python ai/test_gesture_object.py --num-hands 2
```

Gesture만 테스트:

```bash
python ai/test_gesture.py --model ai/model/gesture_03.task
```

Object detector만 테스트:

```bash
python ai/test_object.py
```

## Evaluation

Gesture dataset 평가는 class별 폴더 구조를 사용합니다.

```bash
python ai/evaluate_gesture_dataset.py \
  --dataset gesture_dataset3 \
  --model ai/model/gesture_03.task
```

Object dataset 평가는 `train/labels.json`, `validation/labels.json`,
`images/` 폴더를 가진 COCO-style dataset을 사용합니다.

```bash
python ai/evaluate_object_dataset.py \
  --dataset object_dataset5 \
  --split all \
  --model ai/model/object_08.tflite
```

`labels.json`이 없고 파일명에 label이 들어있는 이미지셋은 filename label 기반으로 평가할 수 있습니다.

```bash
python ai/evaluate_object_dataset2.py \
  --dataset gesture_dataset2 \
  --model ai/model/object_08.tflite
```

평가 결과는 기본적으로 `evaluation_results/` 아래에 CSV, JSON, confusion matrix 이미지로 저장됩니다.

## Notes

- 학습용 dataset과 raw image는 repository에 포함하지 않습니다.
- 학습 pipeline은 추후 별도 PR에서 정리합니다.
- 모델 성능 개선 시 새 모델 파일과 평가 결과를 함께 업데이트합니다.
