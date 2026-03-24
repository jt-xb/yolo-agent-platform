"""
Grounding DINO + SAM 自动标注服务（支持 YOLOv8 回退）

优先尝试导入 Grounding DINO + SAM，失败时回退到 YOLOv8 自动标注。
YOLOv8 回退模式：
  - 使用预训练 YOLOv8 检测图像中的对象
  - 将检测到的类别映射到用户提供的 class_names
  - 如果没有匹配的类别，使用 "object" 类别
"""
import os
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

__all__ = [
    "is_available",
    "get_info",
    "annotate_image",
    "annotate_dataset",
]

# 尝试导入
DINO_AVAILABLE = False
SAM_AVAILABLE = False
_load_err = ""

try:
    from groundingdino.util.utils import build_model
    DINO_AVAILABLE = True
except ImportError as e:
    _load_err += "GroundingDINO: " + str(e) + "; "

try:
    from segment_anything import sam_model_registry, SamPredictor
    SAM_AVAILABLE = True
except ImportError as e:
    _load_err += "SAM: " + str(e) + "; "

# 模型缓存路径
DINO_CACHE = Path(os.path.expanduser("~/.cache/groundingdino"))
SAM_CACHE = Path(os.path.expanduser("~/.cache/sam"))

# YOLOv8 回退标注器（延迟加载）
_yolo_labeler = None


def _get_yolo_labeler():
    """获取或创建 YOLOv8 回退标注器"""
    global _yolo_labeler
    if _yolo_labeler is None:
        try:
            from ultralytics import YOLO
            _yolo_labeler = YOLO("yolov8n.pt")
        except Exception as e:
            _yolo_labeler = None
    return _yolo_labeler


def _yolo_annotate_image(
    image_path: str,
    class_names: List[str],
    box_threshold: float = 0.25,
) -> List[Dict]:
    """
    使用 YOLOv8 作为回退方案进行自动标注。

    策略：
    1. 用 YOLOv8n 预训练模型检测图像中的所有对象
    2. 将检测到的类名与用户提供的 class_names 进行模糊匹配
       （支持中文别名，如 "人"→"person"，"车"→"car"）
    3. 匹配的对象用提供的类别名保存；未匹配的用 "object" 或第一个 class_name 保存
    """
    model = _get_yolo_labeler()
    if model is None:
        return []

    # 中文别名映射（用户输入的 class_names 可能是中文）
    CHINESE_ALIAS = {
        "人": "person", "人物": "person", "行人": "person",
        "车": "car", "汽车": "car", "车辆": "car",
        "自行车": "bicycle", "摩托": "motorcycle", "摩托车": "motorcycle",
        "飞机": "airplane", "巴士": "bus", "公交车": "bus",
        "火车": "train", "卡车": "truck", "船": "boat",
        "狗": "dog", "猫": "cat", "马": "horse", "牛": "cow",
        "羊": "sheep", "猪": "pig",
        "安全帽": "helmet", "头盔": "helmet",
        "无安全帽": "no_helmet", "未戴头盔": "no_helmet",
        "火焰": "fire", "火": "fire",
        "烟雾": "smoke", "烟": "smoke",
        "口罩": "mask", "面罩": "mask",
    }

    def normalize(name: str) -> str:
        """标准化类名为英文小写"""
        n = name.lower().strip()
        return CHINESE_ALIAS.get(n, n)

    # 建立用户类别集合
    user_classes_lower = {normalize(c) for c in class_names}
    user_classes_list = list(user_classes_lower)

    # YOLOv8 预训练类别（COCO 80 类）
    coco_names = {
        0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
        5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light",
        10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench",
        14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
        20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack",
        25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee",
        30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite", 34: "baseball bat",
        35: "baseball glove", 36: "skateboard", 37: "surfboard", 38: "tennis racket",
        39: "bottle", 40: "wine glass", 41: "cup", 42: "fork", 43: "knife",
        44: "spoon", 45: "bowl", 46: "banana", 47: "apple", 48: "sandwich",
        49: "orange", 50: "broccoli", 51: "carrot", 52: "hot dog", 53: "pizza",
        54: "donut", 55: "cake", 56: "chair", 57: "couch", 58: "potted plant",
        59: "bed", 60: "dining table", 61: "toilet", 62: "tv", 63: "laptop",
        64: "mouse", 65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave",
        69: "oven", 70: "toaster", 71: "sink", 72: "refrigerator", 73: "book",
        74: "clock", 75: "vase", 76: "scissors", 77: "teddy bear", 78: "hair drier",
        79: "toothbrush",
    }

    try:
        results = model.predict(
            source=image_path,
            conf=box_threshold,
            verbose=False,
            device='cpu',
        )
    except Exception:
        return []

    if not results or len(results) == 0:
        return []

    r = results[0]
    if r.boxes is None:
        return []

    h, w = r.boxes.orig_shape if hasattr(r.boxes, 'orig_shape') else (640, 640)

    annotations = []
    for box in r.boxes:
        cls_id = int(box.cls.item())
        conf = float(box.conf.item())
        # xywhn: normalized [x_center, y_center, w, h]
        xywhn = box.xywhn[0].tolist()

        detected_name = coco_names.get(cls_id, f"class_{cls_id}")
        normalized_detected = normalize(detected_name)

        # 匹配到用户类别
        if normalized_detected in user_classes_lower:
            label = class_names[list(user_classes_lower).index(normalized_detected)]
        elif any(normalized_detected in uc or uc in normalized_detected for uc in user_classes_lower):
            # 模糊匹配
            for i, uc in enumerate(user_classes_lower):
                if normalized_detected in uc or uc in normalized_detected:
                    label = class_names[i]
                    break
            else:
                label = class_names[0] if class_names else "object"
        else:
            # 未匹配到用户类别，跳过或用第一个类别
            label = class_names[0] if class_names else "object"

        annotations.append({
            "bbox": [round(v, 6) for v in xywhn],
            "label": label,
            "confidence": round(conf, 3),
        })

    return annotations


def _load_dino() -> Any:
    """加载 Grounding DINO 模型"""
    if not DINO_AVAILABLE:
        raise RuntimeError("GroundingDINO 不可用: " + _load_err)

    checkpoint = DINO_CACHE / "groundingdino_swint_ogc.pth"
    if not checkpoint.exists():
        checkpoint = DINO_CACHE / "groundingdino_base.pth"
    if not checkpoint.exists():
        raise FileNotFoundError("GroundingDINO 模型文件未找到，请下载模型到: " + str(DINO_CACHE))

    config_candidates = list(DINO_CACHE.glob("*.py")) + list(Path("/tmp/groundingdino/config").glob("*.py"))
    if config_candidates:
        config_path = str(config_candidates[0])
        model = build_model(config_path, str(checkpoint))
        return model
    raise FileNotFoundError("GroundingDINO 配置文件未找到")


def _load_sam(model_type="vit_b") -> Any:
    """加载 SAM 模型"""
    if not SAM_AVAILABLE:
        raise RuntimeError("SAM 不可用: " + _load_err)

    sam_file = SAM_CACHE / ("sam_" + model_type + "_01ec64.pth")
    if not sam_file.exists():
        sam_file = SAM_CACHE / "sam_vit_b_01ec64.pth"
    if not sam_file.exists():
        raise FileNotFoundError("SAM 模型文件未找到: " + str(SAM_CACHE))

    model = sam_model_registry[model_type](checkpoint=str(sam_file))
    return SamPredictor(model)


def dino_detect(
    model: Any,
    image: np.ndarray,
    text_prompt: str,
    box_thr: float = 0.25,
    text_thr: float = 0.25,
) -> Tuple[List, List, List]:
    """
    使用 Grounding DINO 检测

    Args:
        model: 已加载的 DINO 模型
        image: RGB 图像 (H,W,3)
        text_prompt: 如 "person.helmet.no_helmet"
        box_thr: 框置信度阈值
        text_thr: 文本阈值

    Returns:
        (boxes_px, labels, scores)  boxes_px = [[x1,y1,x2,y2], ...] 像素坐标
    """
    import torch
    from PIL import Image

    h, w = image.shape[:2]
    image_pil = Image.fromarray(image)

    with torch.no_grad():
        outputs = model([image_pil], captions=[text_prompt])

    logits = outputs["pred_logits"].cpu().sigmoid()[0]
    boxes = outputs["pred_boxes"].cpu()[0]
    scores = logits.max(dim=1)[0].numpy()

    phrases = []
    raw_phrases = outputs.get("pred_phrases", [])
    for phrase in raw_phrases:
        if isinstance(phrase, dict):
            phrases.append(phrase.get("text", "object"))
        elif isinstance(phrase, (list, tuple)):
            phrases.append(str(phrase[0]) if phrase[0] else "object")
        else:
            phrases.append(str(phrase))

    result_boxes = []
    result_labels = []
    result_scores = []

    for i, (box, score) in enumerate(zip(boxes, scores)):
        if float(score) < box_thr:
            continue
        cx, cy, bw, bh = box.numpy()
        x1 = max(0, int((cx - bw / 2) * w))
        y1 = max(0, int((cy - bh / 2) * h))
        x2 = min(w, int((cx + bw / 2) * w))
        y2 = min(h, int((cy + bh / 2) * h))
        if x2 > x1 and y2 > y1:
            result_boxes.append(np.array([x1, y1, x2, y2]))
            result_labels.append(phrases[i] if i < len(phrases) else "object")
            result_scores.append(float(score))

    return result_boxes, result_labels, result_scores


def sam_refine(
    predictor: Any,
    image: np.ndarray,
    boxes: List,
    labels: List,
    scores: List,
) -> List[Dict]:
    """
    用 SAM 精化边界框（从掩码计算最小外接矩形）

    Returns:
        [{"bbox": [cx,cy,w,h], "label": str, "confidence": float}, ...]
        bbox 为 YOLO 归一化格式 (0-1)
    """
    if predictor is None or len(boxes) == 0:
        h, w = image.shape[:2]
        return [
            {
                "bbox": [
                    float((boxes[i][0] + boxes[i][2]) / 2 / w),
                    float((boxes[i][1] + boxes[i][3]) / 2 / h),
                    float((boxes[i][2] - boxes[i][0]) / w),
                    float((boxes[i][3] - boxes[i][1]) / h),
                ],
                "label": labels[i],
                "confidence": float(scores[i]),
            }
            for i in range(len(boxes))
        ]

    predictor.set_image(image)
    refined = []

    for box, label, score in zip(boxes, labels, scores):
        try:
            x1, y1, x2, y2 = [int(v) for v in box]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            mask, _, _ = predictor.predict(
                point_coords=np.array([[cx, cy]]),
                point_labels=np.array([1]),
                box=np.array([[x1, y1, x2, y2]]),
                multimask_output=False,
            )
            mask = mask[0]
            ys, xs = np.where(mask)
            if len(xs) > 0 and len(ys) > 0:
                rx1, ry1 = xs.min(), ys.min()
                rx2, ry2 = xs.max(), ys.max()
            else:
                rx1, ry1, rx2, ry2 = x1, y1, x2, y2
        except Exception:
            rx1, ry1, rx2, ry2 = x1, y1, x2, y2

        h, w = image.shape[:2]
        refined.append({
            "bbox": [
                round(float((rx1 + rx2) / 2 / w), 6),
                round(float((ry1 + ry2) / 2 / h), 6),
                round(float((rx2 - rx1) / w), 6),
                round(float((ry2 - ry1) / h), 6),
            ],
            "label": label,
            "confidence": round(float(score), 3),
        })

    return refined


def annotate_image(
    image_path: str,
    class_names: List[str],
    box_threshold: float = 0.25,
) -> List[Dict]:
    """
    对单张图片进行自动标注。

    优先使用 Grounding DINO + SAM（如果可用），否则使用 YOLOv8 回退。

    Args:
        image_path: 图片路径
        class_names: 类别列表，如 ["person", "helmet", "no_helmet"]
        box_threshold: 置信度阈值

    Returns:
        [{"bbox": [cx,cy,w,h], "label": str, "confidence": float}, ...]
    """
    if not os.path.exists(image_path):
        return []

    # 如果 Grounding DINO 可用，使用 DINO + SAM
    if DINO_AVAILABLE:
        try:
            img = cv2.imread(image_path)
            if img is None:
                return []
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            dino_model = _load_dino()
            sam_pred = _load_sam()

            text_prompt = ".".join(class_names)
            boxes, labels, scores = dino_detect(dino_model, img_rgb, text_prompt, box_threshold)

            if not boxes:
                return []

            return sam_refine(sam_pred, img_rgb, boxes, labels, scores)
        except Exception as e:
            # DINO/SAM 失败，回退到 YOLOv8
            print(f"[AutoLabel] DINO/SAM failed ({e}), falling back to YOLOv8")

    # YOLOv8 回退
    return _yolo_annotate_image(image_path, class_names, box_threshold)


def annotate_dataset(
    image_paths: List[str],
    class_names: List[str],
    output_dir: str,
    class_name_to_id: Dict[str, int],
    box_threshold: float = 0.25,
    progress_callback=None,
) -> Dict[str, Any]:
    """
    对整个数据集进行自动标注

    Args:
        image_paths: 图片路径列表
        class_names: 类别列表
        output_dir: 标注文件输出目录（每个图片对应同名 .txt）
        class_name_to_id: 类别名到 ID 的映射
        box_threshold: 置信度阈值
        progress_callback: (current, total) -> None

    Returns:
        {"success": True, "total": int, "annotated": int,
         "failed": int, "total_objects": int}
    """
    os.makedirs(output_dir, exist_ok=True)

    # 尝试使用 DINO + SAM
    dino_model = None
    sam_pred = None
    use_dino = DINO_AVAILABLE

    if use_dino:
        try:
            dino_model = _load_dino()
            sam_pred = _load_sam()
        except Exception as e:
            print(f"[AutoLabel] DINO/SAM load failed ({e}), using YOLOv8 fallback")
            use_dino = False

    total = len(image_paths)
    annotated = 0
    failed = 0
    total_objects = 0

    for i, img_path in enumerate(image_paths):
        try:
            if use_dino and dino_model is not None:
                img = cv2.imread(img_path)
                if img is None:
                    failed += 1
                    continue
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                boxes, labels, scores = dino_detect(
                    dino_model, img_rgb, ".".join(class_names), box_threshold
                )
                results = sam_refine(sam_pred, img_rgb, boxes, labels, scores)
            else:
                results = _yolo_annotate_image(img_path, class_names, box_threshold)

            if results:
                annotated += 1
                total_objects += len(results)

            # 保存 YOLO 格式
            img_name = Path(img_path).stem
            out_path = os.path.join(output_dir, img_name + ".txt")
            with open(out_path, "w") as f:
                lines = []
                for r in results:
                    cid = class_name_to_id.get(r["label"], 0)
                    bbox = r["bbox"]
                    lines.append(str(cid) + " " +
                                " ".join([str(round(v, 6)) for v in bbox]))
                f.write("\n".join(lines))

        except Exception as e:
            failed += 1
            print(f"[AutoLabel] Failed to annotate {img_path}: {e}")

        if progress_callback:
            progress_callback(i + 1, total)

    return {
        "success": True,
        "total": total,
        "annotated": annotated,
        "failed": failed,
        "total_objects": total_objects,
    }


def is_available() -> bool:
    """是否有可用的真实 DINO+SAM 模型"""
    return DINO_AVAILABLE and SAM_AVAILABLE


def is_yolo_available() -> bool:
    """YOLOv8 回退是否可用"""
    return _get_yolo_labeler() is not None


def get_info() -> Dict[str, Any]:
    return {
        "available": is_available(),
        "yolo_fallback": is_yolo_available(),
        "dino_ok": DINO_AVAILABLE,
        "sam_ok": SAM_AVAILABLE,
        "load_error": _load_err if not is_available() else "",
        "dino_cache": str(DINO_CACHE),
        "sam_cache": str(SAM_CACHE),
        "mode": "dino_sam" if is_available() else "yolov8_fallback",
    }
