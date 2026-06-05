// CV 자산(모델 + MediaPipe WASM)을 frontend/public/ 아래로 복사한다.
//  - 모델: ai/model/*  →  public/models/            (브라우저가 /models/* 로 fetch)
//  - WASM: node_modules/@mediapipe/tasks-vision/wasm/*  →  public/mediapipe-wasm/
//    (FilesetResolver가 /mediapipe-wasm 에서 로드. node_modules와 같은 버전이라
//     CDN 버전 불일치 로더 에러가 없고, 오프라인에서도 동작.)
// predev / prebuild 훅에서 자동 실행. 복사본은 전부 gitignore(대용량 중복 방지).
import { copyFile, mkdir, stat, readdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url)); // frontend/scripts
const frontend = resolve(here, "..");
const repoRoot = resolve(frontend, "..");

// 크기가 같으면 이미 최신으로 보고 스킵(재실행 빠르게).
async function copyIfChanged(src, dest) {
  if (existsSync(dest)) {
    const [s, d] = await Promise.all([stat(src), stat(dest)]);
    if (s.size === d.size) return false;
  }
  await copyFile(src, dest);
  return true;
}

// 1) 모델 파일
{
  const srcDir = resolve(repoRoot, "ai", "model");
  const destDir = resolve(frontend, "public", "models");
  await mkdir(destDir, { recursive: true });
  for (const name of ["gesture_03.task", "object_04.tflite"]) {
    const src = resolve(srcDir, name);
    if (!existsSync(src)) {
      console.error(`[copy-models] 소스 모델 없음: ${src}`);
      process.exitCode = 1;
      continue;
    }
    const copied = await copyIfChanged(src, resolve(destDir, name));
    console.log(`[copy-models] ${copied ? "복사됨" : "스킵 "}: models/${name}`);
  }
}

// 2) MediaPipe WASM (설치된 버전 그대로 복사 → JS 번들과 버전 일치 보장)
{
  const srcDir = resolve(frontend, "node_modules", "@mediapipe", "tasks-vision", "wasm");
  const destDir = resolve(frontend, "public", "mediapipe-wasm");
  if (!existsSync(srcDir)) {
    console.error(`[copy-models] WASM 폴더 없음(@mediapipe/tasks-vision 미설치?): ${srcDir}`);
    process.exitCode = 1;
  } else {
    await mkdir(destDir, { recursive: true });
    for (const name of await readdir(srcDir)) {
      const copied = await copyIfChanged(resolve(srcDir, name), resolve(destDir, name));
      if (copied) console.log(`[copy-models] 복사됨: mediapipe-wasm/${name}`);
    }
  }
}
