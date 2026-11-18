import type { ObjectDetector } from "@mediapipe/tasks-vision";

// Lab only. The model and runtime are downloaded by the browser; no video leaves this device for analysis.
// EfficientDet-Lite0 (Apache-2.0) is COCO-trained: it knows "person" and "cell phone", nothing about needles.
const WASM_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.0/wasm";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/int8/1/efficientdet_lite0.tflite";

export type Box = { label: "person" | "cell phone"; score: number; x: number; y: number; w: number; h: number };

export async function loadDetector(): Promise<ObjectDetector> {
  const { FilesetResolver, ObjectDetector } = await import("@mediapipe/tasks-vision");
  const files = await FilesetResolver.forVisionTasks(WASM_URL);
  return ObjectDetector.createFromOptions(files, {
    baseOptions: { modelAssetPath: MODEL_URL },
    runningMode: "VIDEO",
    scoreThreshold: 0.3,
    categoryAllowlist: ["person", "cell phone"],
  });
}

export function detect(detector: ObjectDetector, video: HTMLVideoElement, nowMs: number): Box[] {
  return detector.detectForVideo(video, nowMs).detections.flatMap((d) => {
    const c = d.categories[0];
    const b = d.boundingBox;
    if (!c || !b || (c.categoryName !== "person" && c.categoryName !== "cell phone")) return [];
    return [{ label: c.categoryName, score: c.score, x: b.originX, y: b.originY, w: b.width, h: b.height }];
  });
}

export const best = (boxes: Box[], label: Box["label"]) => Math.max(0, ...boxes.filter((b) => b.label === label).map((b) => b.score));
