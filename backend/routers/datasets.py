"""
数据集管理 API
"""
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Body
from typing import Annotated
from sqlalchemy.orm import Session

from backend.core.database import get_db, Dataset
from backend.core.config import settings
from backend.services.auto_annotation import get_auto_annotation_service

router = APIRouter(prefix="/api/datasets", tags=["数据集管理"])


@router.get("/list")
def list_datasets(db: Session = Depends(get_db)):
    """列出所有数据集"""
    datasets = db.query(Dataset).all()
    return {"datasets": [d.to_dict() for d in datasets]}


@router.get("/demo")
def get_demo_dataset():
    """
    获取演示数据集信息
    包含图片列表和标注结果
    """
    dataset_path = Path("/tmp/yolo_demo_dataset")

    if not dataset_path.exists():
        return {"success": False, "message": "数据集不存在"}

    # 获取所有训练图片
    train_img_dir = dataset_path / "images" / "train"
    val_img_dir = dataset_path / "images" / "val"
    train_label_dir = dataset_path / "labels" / "train"
    val_label_dir = dataset_path / "labels" / "val"

    def load_label(label_path):
        """加载YOLO标注文件"""
        if not label_path.exists():
            return []
        boxes = []
        with open(label_path, 'r') as f:
            for line in f.readlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls_id = int(parts[0])
                    x, y, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    # COCO128 类别名
                    names = ['person', 'bicycle', 'car', 'motorcycle', 'airplane']
                    cls_name = names[cls_id] if cls_id < len(names) else f"class_{cls_id}"
                    boxes.append({
                        "class_id": cls_id,
                        "class_name": cls_name,
                        "bbox": [round(x, 4), round(y, 4), round(w, 4), round(h, 4)],
                    })
        return boxes

    def build_image_list(img_dir, label_dir, split):
        """构建图片列表"""
        images = []
        if not img_dir.exists():
            return images
        for img_file in sorted(img_dir.glob("*.jpg"))[:20]:  # 最多20张
            label_file = label_dir / f"{img_file.stem}.txt"
            boxes = load_label(label_file)
            images.append({
                "id": img_file.stem,
                "filename": img_file.name,
                "path": str(img_file.resolve()),
                "url": f"/api/datasets/image/{img_file.stem}",
                "split": split,
                "num_objects": len(boxes),
                "boxes": boxes,
            })
        return images

    train_images = build_image_list(train_img_dir, train_label_dir, "train")
    val_images = build_image_list(val_img_dir, val_label_dir, "val")

    return {
        "success": True,
        "dataset": {
            "id": "demo",
            "name": "安全帽演示数据集",
            "path": str(dataset_path.resolve()),
            "description": "包含 person、helmet、no_helmet 类别的合成数据集",
            "total_images": len(train_images) + len(val_images),
            "train_count": len(train_images),
            "val_count": len(val_images),
            "class_names": ["person", "bicycle", "car", "motorcycle", "airplane"],
            "images": train_images + val_images,
        }
    }


@router.get("/image/{image_id}")
def get_image(image_id: str):
    """
    获取图片文件（用于前端展示）
    """
    # 查找图片
    dataset_path = Path("/tmp/yolo_demo_dataset")
    possible_paths = list(dataset_path.glob(f"**/{image_id}.jpg"))
    if not possible_paths:
        possible_paths = list(dataset_path.glob(f"**/{image_id}.png"))

    if not possible_paths:
        raise HTTPException(status_code=404, detail="图片不存在")

    img_path = possible_paths[0]
    from fastapi.responses import FileResponse
    return FileResponse(str(img_path), media_type="image/jpeg")


@router.get("/{dataset_id}/images")
def get_dataset_images(dataset_id: str, split: str = None):
    """
    获取数据集中的图片列表
    """
    # demo 数据集用专门的接口
    if dataset_id == "demo" or dataset_id == "1":
        demo = get_demo_dataset()
        images = demo["dataset"]["images"]
        if split:
            images = [img for img in images if img["split"] == split]
        return {"images": images, "total": len(images)}

    # 从 data/datasets/{dataset_id} 或 /tmp/{dataset_id} 加载
    dataset_path = None
    for base in [settings.datasets_dir, Path("/tmp")]:
        p = base / dataset_id
        if p.exists():
            dataset_path = p
            break

    if not dataset_path or not dataset_path.exists():
        raise HTTPException(status_code=404, detail="数据集不存在")

    meta = _get_dataset_meta(dataset_path)

    images = []
    for sp in ["train", "val", "test"]:
        img_dir = dataset_path / "images" / sp
        lbl_dir = dataset_path / "labels" / sp
        if not img_dir.exists():
            continue
        for img in sorted(img_dir.glob("*")):
            if img.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                continue
            lbl_file = lbl_dir / f"{img.stem}.txt"
            boxes = _load_boxes(lbl_file)
            images.append({
                "id": img.stem,
                "filename": img.name,
                "path": str(img),
                "url": f"/api/datasets/file/{dataset_id}/{sp}/{img.name}",
                "split": sp,
                "num_objects": len(boxes),
                "boxes": boxes,
            })

    if split:
        images = [img for img in images if img["split"] == split]
    return {"images": images, "total": len(images), "class_names": meta.get("class_names", ["object"])}


@router.get("/{dataset_id}/annotations")
def get_dataset_annotations(dataset_id: str, image_id: str = None):
    """
    获取标注结果
    如果指定 image_id，返回单张图片的标注
    否则返回所有图片的标注摘要
    """
    demo = get_demo_dataset()
    images = demo["dataset"]["images"]

    if image_id:
        for img in images:
            if img["id"] == image_id:
                return {
                    "image_id": image_id,
                    "boxes": img["boxes"],
                    "num_objects": img["num_objects"],
                }
        raise HTTPException(status_code=404, detail="图片不存在")

    # 返回所有图片的标注统计
    return {
        "total_images": len(images),
        "total_objects": sum(img["num_objects"] for img in images),
        "images": [{"id": img["id"], "num_objects": img["num_objects"]} for img in images],
    }


@router.post("/upload-images")
async def upload_images(dataset_id: str = "demo", files: List[UploadFile] = File(...)):
    """
    上传图片到数据集（支持 ZIP 包自动解压）
    """
    # 确定目标目录
    if dataset_id == "demo":
        dataset_path = Path("/tmp/yolo_demo_dataset")
    else:
        dataset_path = Path(f"/tmp/{dataset_id}")

    # 允许 ZIP 上传：优先从 ZIP 解压，ZIP 内图片放入 train
    zip_files = []
    other_files = []

    for f in files:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext == '.zip':
            zip_files.append(f)
        elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
            other_files.append(f)

    uploaded = []

    # 处理 ZIP 文件
    for f in zip_files:
        zip_path = dataset_path / f"{uuid.uuid4().hex[:8]}.zip"
        try:
            with open(zip_path, "wb") as out:
                shutil.copyfileobj(f.file, out)
            with zipfile.ZipFile(zip_path, 'r') as z:
                for member in z.namelist():
                    if member.startswith('__MACOSX') or '/__MACOSX/' in member:
                        continue
                    ext = Path(member).suffix.lower()
                    if ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                        continue
                    data = z.read(member)
                    img_name = f"{uuid.uuid4().hex[:8]}{ext}"
                    img_dir = dataset_path / "images" / "train"
                    img_dir.mkdir(parents=True, exist_ok=True)
                    img_path = img_dir / img_name
                    img_path.write_bytes(data)
                    # 生成空白标注
                    lbl_dir = dataset_path / "labels" / "train"
                    lbl_dir.mkdir(parents=True, exist_ok=True)
                    lbl_file = lbl_dir / f"{img_path.stem}.txt"
                    lbl_file.touch()
                    uploaded.append({
                        "id": img_path.stem,
                        "filename": member,
                        "path": str(img_path),
                        "url": f"/api/datasets/file/{dataset_id}/train/{img_name}",
                        "split": "train",
                    })
            zip_path.unlink()
        except Exception as e:
            print(f"解压失败 {f.filename}: {e}")

    # 处理普通图片
    img_dir = dataset_path / "images" / "train"
    lbl_dir = dataset_path / "labels" / "train"
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    for f in other_files:
        ext = Path(f.filename).suffix.lower()
        new_name = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = img_dir / new_name
        try:
            with open(file_path, "wb") as out:
                shutil.copyfileobj(f.file, out)
            # 生成空白标注文件
            lbl_file = lbl_dir / f"{file_path.stem}.txt"
            lbl_file.touch()
            uploaded.append({
                "id": file_path.stem,
                "filename": f.filename,
                "path": str(file_path),
                "url": f"/api/datasets/file/{dataset_id}/train/{new_name}",
                "split": "train",
            })
        except Exception as e:
            print(f"上传失败 {f.filename}: {e}")

    return {
        "success": True,
        "uploaded_count": len(uploaded),
        "images": uploaded,
    }


@router.delete("/image/{image_id}")
def delete_image(image_id: str):
    """删除图片"""
    dataset_path = Path("/tmp/yolo_demo_dataset")
    possible_paths = list(dataset_path.glob(f"**/{image_id}.jpg"))

    if not possible_paths:
        raise HTTPException(status_code=404, detail="图片不存在")

    img_path = possible_paths[0]
    label_path = img_path.parent.parent / "labels" / img_path.parent.name / f"{img_path.stem}.txt"

    try:
        img_path.unlink()
        if label_path.exists():
            label_path.unlink()
    except Exception as e:
        return {"success": False, "message": str(e)}

    return {"success": True, "message": f"已删除 {img_path.name}"}


@router.post("/dino-sam-auto-label")
async def dino_sam_auto_label(
    body: Annotated[dict, Body()],
):
    """
    使用 Grounding DINO + SAM 对数据集图片进行自动标注（真实 AI 标注）

    task_description: 任务描述（如"检测未佩戴安全帽的人员"）
    class_names: 类别列表，如 ["person", "helmet", "no_helmet"]
    dataset_id: 数据集 ID，默认 demo
    image_ids: 可选，要标注的图片ID列表，默认标注全部
    box_threshold: 置信度阈值（0-1）
    """
    from backend.services.grounding_dino_sam import (
        annotate_image,
        annotate_dataset,
        is_available,
        is_yolo_available,
        get_info,
    )

    # 从 body 中提取参数
    task_description = body.get("task_description", "")
    class_names = body.get("class_names", [])
    dataset_id = body.get("dataset_id", "demo")
    image_ids = body.get("image_ids")
    box_threshold = body.get("box_threshold", 0.25)

    info = get_info()
    mode = info.get("mode", "unknown")

    # 获取数据集图片路径
    if dataset_id == "demo":
        dataset_path = Path("/tmp/yolo_demo_dataset")
    else:
        dataset_path = Path(f"/tmp/{dataset_id}")

    if not dataset_path.exists():
        return {"success": False, "message": f"数据集 {dataset_id} 不存在"}

    split = body.get("split", "train")
    img_dir = dataset_path / "images" / split
    all_images = sorted(img_dir.glob("*.jpg")) if img_dir.exists() else []

    if image_ids:
        images_to_label = [p for p in all_images if p.stem in set(image_ids)]
    else:
        images_to_label = all_images

    if not images_to_label:
        return {"success": False, "message": "没有找到要标注的图片"}

    # 构建 class_name 到 id 的映射
    class_name_to_id = {name: i for i, name in enumerate(class_names)}

    # 标注结果：直接保存到 train split 的 labels 目录（与训练打通）
    label_dir = dataset_path / "labels" / split
    label_dir.mkdir(parents=True, exist_ok=True)

    total = len(images_to_label)
    annotated = 0
    failed = 0
    total_objects = 0
    annotated_images = []

    for img_path in images_to_label:
        try:
            results = annotate_image(
                str(img_path),
                class_names,
                box_threshold=box_threshold,
            )

            if results:
                annotated += 1
                total_objects += len(results)

            # 保存 YOLO 格式标注
            img_stem = img_path.stem
            out_path = label_dir / f"{img_stem}.txt"
            with open(out_path, "w") as f:
                lines = []
                for r in results:
                    cid = class_name_to_id.get(r["label"], 0)
                    bbox = r["bbox"]
                    lines.append(str(cid) + " " + " ".join([str(round(v, 6)) for v in bbox]))
                f.write("\n".join(lines))

            # 转换为前端格式
            boxes = []
            for r in results:
                cid = class_name_to_id.get(r["label"], 0)
                boxes.append({
                    "class_id": cid,
                    "class_name": r["label"],
                    "bbox": r["bbox"],
                    "confidence": r["confidence"],
                })

            annotated_images.append({
                "id": img_stem,
                "filename": f"{img_stem}.jpg",
                "url": f"/api/datasets/image/{img_stem}",
                "split": "train",
                "num_objects": len(results),
                "boxes": boxes,
            })

        except Exception as e:
            failed += 1
            print(f"[DINO-SAM] Failed to annotate {img_path}: {e}")

    return {
        "success": True,
        "message": f"{mode} 自动标注完成！标注了 {annotated}/{total} 张图片，发现 {total_objects} 个目标",
        "mode": mode,
        "dino_available": info.get("dino_ok", False),
        "sam_available": info.get("sam_ok", False),
        "yolo_fallback": info.get("yolo_fallback", False),
        "task_description": task_description,
        "class_names": class_names,
        "box_threshold": box_threshold,
        "total": total,
        "annotated": annotated,
        "failed": failed,
        "total_objects": total_objects,
        "images": annotated_images,
    }


@router.get("/auto-label-info")
def get_auto_label_info():
    """
    获取自动标注服务状态信息
    """
    try:
        from backend.services.grounding_dino_sam import get_info
        return {"success": True, "info": get_info()}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/yolo-auto-label")
async def yolo_auto_label(
    model_path: Optional[str] = None,
    image_ids: Optional[List[str]] = None,
    conf_threshold: float = 0.25,
):
    """
    使用 YOLO 模型对数据集图片进行自动标注

    model_path: 可选，指定模型路径（如训练产出的 best.pt）
    image_ids: 可选，要标注的图片ID列表，默认标注全部
    conf_threshold: 置信度阈值（0-1）
    """
    from backend.services.auto_labeling import get_auto_labeler

    labeler = get_auto_labeler()

    # 尝试加载指定模型或使用预训练模型
    model_loaded = False
    if model_path and os.path.exists(model_path):
        model_loaded = labeler.load_model(model_path)

    if not model_loaded:
        # 使用 ultralytics 内置预训练模型
        try:
            from ultralytics import YOLO
            labeler.model = YOLO("yolov8n.pt")
            labeler.model_path = "yolov8n (pretrained)"
            model_loaded = True
        except Exception as e:
            return {"success": False, "message": f"无法加载模型: {e}"}

    # 获取数据集图片
    dataset_path = Path("/tmp/yolo_demo_dataset")
    img_dir = dataset_path / "images" / "train"

    all_images = sorted(img_dir.glob("*.jpg")) if img_dir.exists() else []

    if image_ids:
        images_to_label = [p for p in all_images if p.stem in set(image_ids)]
    else:
        images_to_label = all_images

    if not images_to_label:
        return {"success": False, "message": "没有找到要标注的图片"}

    # 执行 YOLO 自动标注
    image_paths = [str(p) for p in images_to_label]

    results = labeler.auto_label_dataset(
        image_paths=image_paths,
        class_names=[],
        conf_threshold=conf_threshold,
    )

    # 保存标注结果到 labels/auto 目录
    label_dir = dataset_path / "labels" / "auto"
    label_dir.mkdir(parents=True, exist_ok=True)

    labeler.save_labels(
        predictions=results["results"],
        output_label_dir=str(label_dir),
        class_names=[],
    )

    # 构建返回数据
    annotated_images = []
    for img_path, preds in results["results"].items():
        img_stem = Path(img_path).stem
        annotated_images.append({
            "id": img_stem,
            "filename": f"{img_stem}.jpg",
            "url": f"/api/datasets/image/{img_stem}",
            "split": "train",
            "num_objects": len(preds),
            "boxes": preds,
        })

    return {
        "success": True,
        "message": f"YOLO 自动标注完成！标注了 {results['annotated']}/{results['total']} 张图片，发现 {results['total_objects']} 个目标",
        "model": labeler.model_path,
        "conf_threshold": conf_threshold,
        "total": results["total"],
        "annotated": results["annotated"],
        "total_objects": results["total_objects"],
        "images": annotated_images,
    }


# ============================================================
# 数据集导入 / 拆分 / 合并
# ============================================================

import zipfile
import random


def _guess_class_names(label_dir: Path, img_dir: Path):
    """从已有的标注文件猜测类别列表"""
    names = set()
    for lbl in label_dir.glob("*.txt"):
        with open(lbl) as f:
            for line in f:
                parts = line.strip().split()
                if parts:
                    cid = int(parts[0])
                    names.add(cid)
    return [f"class_{i}" for i in sorted(names)]


def _find_dataset_path(dataset_id: str) -> Optional[Path]:
    """根据 dataset_id 找到数据集根目录"""
    if dataset_id == "demo":
        return Path("/tmp/yolo_demo_dataset")
    for base in [settings.datasets_dir, Path("/tmp")]:
        p = base / dataset_id
        if p.exists():
            return p
    return None


def _get_dataset_meta(dataset_path: Path) -> dict:
    """读取数据集元信息"""
    meta_file = dataset_path / "dataset_meta.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text())
    # 自动从 labels 推导类名
    lbl_train = dataset_path / "labels" / "train"
    img_train = dataset_path / "images" / "train"
    names = _guess_class_names(lbl_train, img_train)
    return {"class_names": names or ["object"]}


def _save_dataset_meta(dataset_path: Path, meta: dict):
    """保存数据集元信息"""
    meta_file = dataset_path / "dataset_meta.json"
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


def _load_boxes(label_path: Path):
    """加载 YOLO 标注"""
    if not label_path.exists():
        return []
    boxes = []
    for line in open(label_path):
        parts = line.strip().split()
        if len(parts) >= 5:
            boxes.append({
                "class_id": int(parts[0]),
                "bbox": [round(float(parts[i]), 6) for i in range(1, 5)],
            })
    return boxes


def _save_label(label_path: Path, boxes: list):
    """保存 YOLO 标注"""
    label_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for box in boxes:
        lines.append(f"{box['class_id']} {' '.join(str(round(v, 6)) for v in box['bbox'])}")
    label_path.write_text('\n'.join(lines))


@router.post("/import")
async def import_dataset(
    files: List[UploadFile] = File(...),
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
):
    """
    导入图片压缩包或散装图片，自动拆分训练/验证/测试集

    - 支持 .zip 压缩包（自动解压）
    - 支持多张散装图片一起上传
    - 自动分配到 train / val / test 目录
    - 生成空白标注 .txt 文件（待手动标注）
    """
    dataset_id = f"ds_{uuid.uuid4().hex[:8]}"
    dataset_path = Path(f"/tmp/{dataset_id}")
    img_train = dataset_path / "images" / "train"
    img_val = dataset_path / "images" / "val"
    img_test = dataset_path / "images" / "test"
    lbl_train = dataset_path / "labels" / "train"
    lbl_val = dataset_path / "labels" / "val"
    lbl_test = dataset_path / "labels" / "test"

    for d in [img_train, img_val, img_test, lbl_train, lbl_val, lbl_test]:
        d.mkdir(parents=True, exist_ok=True)

    ratios = [train_ratio, val_ratio, test_ratio]
    total = sum(ratios)
    if abs(total - 1.0) > 0.01:
        return {"success": False, "message": f"比例之和必须=1.0，当前={total}"}

    uploaded = []
    tmp_files = []

    for f in files:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext == '.zip':
            # 保存到临时文件再解压
            zip_path = dataset_path / f.filename
            with open(zip_path, "wb") as out:
                shutil.copyfileobj(f.file, out)
            tmp_files.append(zip_path)
        elif ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            # 直接保存图片
            img_name = f"{uuid.uuid4().hex[:8]}{ext}"
            img_path = img_train / img_name  # 先全放训练集，后面再分配
            with open(img_path, "wb") as out:
                shutil.copyfileobj(f.file, out)
            uploaded.append({"filename": f.filename, "saved": str(img_path)})

    # 解压 ZIP
    for zip_path in tmp_files:
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                for member in z.namelist():
                    if member.startswith('__MACOSX') or '/__MACOSX/' in member:
                        continue
                    ext = Path(member).suffix.lower()
                    if ext not in ['.jpg', '.jpeg', '.png', '.bmp']:
                        continue
                    data = z.read(member)
                    img_name = f"{uuid.uuid4().hex[:8]}{ext}"
                    img_path = img_train / img_name
                    img_path.write_bytes(data)
                    uploaded.append({"filename": member, "saved": str(img_path)})
            zip_path.unlink()
        except Exception as e:
            print(f"解压失败 {zip_path}: {e}")

    # 划分 train / val / test
    images = sorted([p for p in img_train.glob("*") if p.suffix.lower() in ['.jpg', '.png', '.bmp', '.jpeg']])
    random.shuffle(images)

    n = len(images)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    split_order = [
        ("train", img_train, lbl_train, images[:n_train]),
        ("val",   img_val,   lbl_val,   images[n_train:n_train + n_val]),
        ("test",  img_test,  lbl_test,  images[n_train + n_val:]),
    ]

    stats = {"train": 0, "val": 0, "test": 0}

    for split_name, img_dir, lbl_dir, imgs in split_order:
        for img_path in imgs:
            # 移动到目标目录（如果不在的话）
            target_path = img_dir / img_path.name
            if img_path != target_path:
                shutil.move(str(img_path), str(target_path))
            # 生成空白标注文件
            lbl_file = lbl_dir / f"{target_path.stem}.txt"
            lbl_file.touch()
            stats[split_name] += 1

    # 尝试从已有标注猜测类别
    all_labels = dataset_path / "labels"
    names = _guess_class_names(lbl_train, img_train)
    if not names:
        names = ["object"]

    return {
        "success": True,
        "dataset_id": dataset_id,
        "message": f"导入完成！共 {len(uploaded)} 张图片 → 训练集 {stats['train']} / 验证集 {stats['val']} / 测试集 {stats['test']}",
        "dataset": {
            "id": dataset_id,
            "name": f"数据集_{dataset_id}",
            "path": str(dataset_path),
            "total_images": len(uploaded),
            "train_count": stats["train"],
            "val_count": stats["val"],
            "test_count": stats["test"],
            "class_names": names,
        },
    }


@router.post("/video-extract")
async def extract_video_frames(
    dataset_id: str = Body(...),
    file: UploadFile = File(...),
    frame_interval: int = Body(5),
    max_frames: int = Body(200),
    split: str = Body("train"),
):
    """
    上传视频文件，按帧间隔抽帧导入数据集

    - 支持 MP4/AVI/MOV/MKV 等常见视频格式
    - frame_interval: 抽帧间隔（每 N 帧抽 1 张），默认 5
    - max_frames: 最多抽帧数量，默认 200
    - split: 保存到 train/val/test，默认 train
    """
    import cv2

    ext = Path(file.filename).suffix.lower()
    if ext not in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']:
        return {"success": False, "message": f"不支持的视频格式: {ext}，支持 MP4/AVI/MOV/MKV"}

    # 创建数据集目录
    dataset_path = Path(f"/tmp/{dataset_id}") if dataset_id != "demo" else Path("/tmp/yolo_demo_dataset")
    img_dir = dataset_path / "images" / split
    lbl_dir = dataset_path / "labels" / split
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    # 保存视频到临时文件
    video_path = dataset_path / f"{uuid.uuid4().hex[:8]}{ext}"
    try:
        with open(video_path, "wb") as out:
            shutil.copyfileobj(file.file, out)
    except Exception as e:
        return {"success": False, "message": f"视频保存失败: {e}"}

    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {"success": False, "message": "无法打开视频文件"}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        extracted = 0
        frame_idx = 0
        saved = 0

        while frame_idx < total_frames and saved < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break

            # 每隔 frame_interval 帧抽一张
            img_name = f"frame_{uuid.uuid4().hex[:8]}_{saved:04d}.jpg"
            img_path = img_dir / img_name
            success = cv2.imwrite(str(img_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if success:
                # 生成空白标注文件
                lbl_file = lbl_dir / f"{img_path.stem}.txt"
                lbl_file.touch()
                saved += 1

            frame_idx += frame_interval

        cap.release()
        video_path.unlink()  # 删除临时视频文件

        return {
            "success": True,
            "message": f"抽帧完成！从 {total_frames} 帧视频中提取 {saved} 张图片（间隔={frame_interval}）",
            "video_info": {
                "total_frames": total_frames,
                "fps": round(fps, 1),
                "duration_sec": round(duration, 2),
                "resolution": f"{width}x{height}",
            },
            "extracted": saved,
            "dataset_id": dataset_id,
            "split": split,
        }

    except Exception as e:
        video_path.unlink(missing_ok=True)
        return {"success": False, "message": f"抽帧失败: {str(e)}"}


@router.post("/merge")
def merge_datasets(
    source_id_1: str,
    source_id_2: str,
    target_name: str = "merged",
):
    """
    合并两个数据集，返回新的合并数据集

    - 将 source_id_1 和 source_id_2 的图片 + 标注合并
    - 生成新的 target_id 数据集
    - 类别取并集
    """
    def get_ds_path(ds_id: str) -> Optional[Path]:
        if ds_id == "demo":
            return Path("/tmp/yolo_demo_dataset")
        p = Path(f"/tmp/{ds_id}")
        return p if p.exists() else None

    p1 = get_ds_path(source_id_1)
    p2 = get_ds_path(source_id_2)

    if not p1:
        raise HTTPException(status_code=404, detail=f"数据集 {source_id_1} 不存在")
    if not p2:
        raise HTTPException(status_code=404, detail=f"数据集 {source_id_2} 不存在")

    target_id = f"ds_{uuid.uuid4().hex[:8]}"
    target = Path(f"/tmp/{target_id}")

    for split in ["train", "val", "test"]:
        (target / "images" / split).mkdir(parents=True, exist_ok=True)
        (target / "labels" / split).mkdir(parents=True, exist_ok=True)

    all_classes = set()

    def merge_split(src_path: Path, tgt_path: Path, split: str):
        src_img = src_path / "images" / split
        src_lbl = src_path / "labels" / split
        tgt_img = tgt_path / "images" / split
        tgt_lbl = tgt_path / "labels" / split
        if not src_img.exists():
            return 0
        for img in src_img.glob("*"):
            ext = img.suffix.lower()
            new_name = f"{uuid.uuid4().hex[:8]}{ext}"
            shutil.copy2(str(img), str(tgt_img / new_name))
            lbl_src = src_lbl / f"{img.stem}.txt"
            lbl_tgt = tgt_lbl / f"{new_name.replace(ext, '.txt')}"
            if lbl_src.exists():
                shutil.copy2(str(lbl_src), str(lbl_tgt))
                # 收集类别
                for line in open(lbl_src):
                    parts = line.strip().split()
                    if parts:
                        all_classes.add(int(parts[0]))
        return len(list(src_img.glob("*")))

    total = sum(merge_split(p1, target, s) + merge_split(p2, target, s)
                for s in ["train", "val", "test"])

    class_names = [f"class_{i}" for i in sorted(all_classes)] or ["object"]

    return {
        "success": True,
        "dataset_id": target_id,
        "message": f"合并完成！共 {total} 张图片 → {target_name}",
        "dataset": {
            "id": target_id,
            "name": target_name,
            "path": str(target),
            "total_images": total,
            "class_names": class_names,
            "merged_from": [source_id_1, source_id_2],
        },
    }


def _scan_dataset_dir(base_path: Path):
    """扫描一个目录，返回数据集列表"""
    datasets = []
    if not base_path.exists():
        return datasets
    for p in sorted(base_path.iterdir()):
        if not p.is_dir():
            continue
        imgs = {}
        total = 0
        for split in ["train", "val", "test"]:
            img_dir = p / "images" / split
            lbl_dir = p / "labels" / split
            cnt = len(list(img_dir.glob("*"))) if img_dir.exists() else 0
            imgs[split] = cnt
            total += cnt
        names = _guess_class_names(p / "labels" / "train", p / "images" / "train")
        datasets.append({
            "id": p.name,
            "name": p.name,
            "path": str(p),
            "total_images": total,
            "train_count": imgs.get("train", 0),
            "val_count": imgs.get("val", 0),
            "test_count": imgs.get("test", 0),
            "class_names": names or ["object"],
        })
    return datasets


@router.get("/all")
def list_all_datasets():
    """列出所有已导入的数据集（从 /tmp/ds_* 和 data/datasets/ 目录）"""
    datasets = []
    # 扫描 /tmp/ds_* 目录
    datasets.extend(_scan_dataset_dir(Path("/tmp")))
    # 扫描 data/datasets/ 目录
    datasets.extend(_scan_dataset_dir(settings.datasets_dir))
    # 加入 demo
    demo = get_demo_dataset()
    if demo.get("success"):
        datasets.insert(0, {
            "id": "demo",
            "name": demo["dataset"]["name"],
            "path": demo["dataset"]["path"],
            "total_images": demo["dataset"]["total_images"],
            "train_count": demo["dataset"]["train_count"],
            "val_count": demo["dataset"]["val_count"],
            "test_count": 0,
            "class_names": demo["dataset"]["class_names"],
        })
    return {"datasets": datasets}


@router.get("/{dataset_id}/meta")
def get_dataset_meta(dataset_id: str):
    """获取数据集元信息（类名等）"""
    dataset_path = _find_dataset_path(dataset_id)
    if not dataset_path:
        raise HTTPException(status_code=404, detail="数据集不存在")
    meta = _get_dataset_meta(dataset_path)
    return meta


@router.put("/{dataset_id}/meta")
def update_dataset_meta(dataset_id: str, body: dict = Body(...)):
    """更新数据集元信息"""
    dataset_path = _find_dataset_path(dataset_id)
    if not dataset_path:
        raise HTTPException(status_code=404, detail="数据集不存在")
    meta = _get_dataset_meta(dataset_path)
    if "class_names" in body:
        meta["class_names"] = body["class_names"]
    _save_dataset_meta(dataset_path, meta)
    return {"success": True, "class_names": meta["class_names"]}


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str):
    """获取指定数据集详情"""
    if dataset_id == "demo":
        return get_demo_dataset()
    p = Path(f"/tmp/{dataset_id}")
    if not p.exists():
        raise HTTPException(status_code=404, detail="数据集不存在")
    images = []
    for split in ["train", "val", "test"]:
        img_dir = p / "images" / split
        lbl_dir = p / "labels" / split
        if not img_dir.exists():
            continue
        for img in sorted(img_dir.glob("*")):
            lbl_file = lbl_dir / f"{img.stem}.txt"
            boxes = _load_boxes(lbl_file)
            images.append({
                "id": f"{dataset_id}_{img.stem}",
                "filename": img.name,
                "path": str(img),
                "url": f"/api/datasets/file/{dataset_id}/{split}/{img.name}",
                "split": split,
                "num_objects": len(boxes),
                "boxes": boxes,
            })
    names = _guess_class_names(p / "labels" / "train", p / "images" / "train")
    return {
        "success": True,
        "dataset": {
            "id": dataset_id,
            "name": dataset_id,
            "path": str(p),
            "total_images": len(images),
            "train_count": len([i for i in images if i["split"] == "train"]),
            "val_count": len([i for i in images if i["split"] == "val"]),
            "test_count": len([i for i in images if i["split"] == "test"]),
            "class_names": names or ["object"],
            "images": images,
        },
    }


@router.get("/file/{dataset_id}/{split}/{filename}")
def get_dataset_file(dataset_id: str, split: str, filename: str):
    """获取数据集中的图片文件"""
    if dataset_id == "demo":
        return get_image(filename.rsplit('.', 1)[0])
    p = Path(f"/tmp/{dataset_id}/images/{split}/{filename}")
    if not p.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    from fastapi.responses import FileResponse
    return FileResponse(str(p), media_type="image/jpeg")


@router.post("/create")
def create_dataset(name: str = Body(..., embed=True)):
    """
    创建一个新的空数据集
    """
    import re
    # 生成安全的 dataset_id
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    dataset_id = f"ds_{safe_name}_{uuid.uuid4().hex[:6]}"
    dataset_path = Path(f"/tmp/{dataset_id}")

    # 创建目录结构
    for split in ["train", "val", "test"]:
        (dataset_path / "images" / split).mkdir(parents=True, exist_ok=True)
        (dataset_path / "labels" / split).mkdir(parents=True, exist_ok=True)

    return {
        "success": True,
        "dataset_id": dataset_id,
        "message": f"数据集 '{name}' 创建成功",
        "dataset": {
            "id": dataset_id,
            "name": name,
            "path": str(dataset_path),
            "total_images": 0,
            "train_count": 0,
            "val_count": 0,
            "test_count": 0,
            "class_names": ["object"],
        }
    }


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str):
    """
    删除数据集
    """
    if dataset_id == "demo":
        return {"success": False, "message": "演示数据集无法删除"}

    dataset_path = Path(f"/tmp/{dataset_id}")
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail="数据集不存在")

    try:
        shutil.rmtree(dataset_path)
        return {"success": True, "message": f"数据集 {dataset_id} 已删除"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/image/{image_id}/annotations")
def save_image_annotations(
    image_id: str,
    boxes: List[dict] = Body(...),
):
    """
    保存图片的手动标注结果

    boxes 格式: [{"class_id": 0, "bbox": [cx, cy, w, h]}, ...]
    bbox 为 YOLO 归一化坐标 [cx, cy, w, h]
    """
    # 解析 image_id 找到对应的图片和数据集
    # 格式可能是: "demo_image001" 或 "ds_xxx_image001" 或直接是 "image001" (for demo)
    dataset_path = Path("/tmp/yolo_demo_dataset")

    # 尝试在 demo 数据集找
    img_path = None
    for split in ["train", "val", "test"]:
        img_dir = dataset_path / "images" / split
        if img_dir.exists():
            for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                potential = img_dir / f"{image_id}{ext}"
                if potential.exists():
                    img_path = potential
                    break
        if img_path:
            break

    # 如果 demo 里没找到，尝试其他数据集（/tmp/ds_* 和 data/datasets/）
    if not img_path:
        search_dirs = list(Path("/tmp").glob("ds_*")) + list(settings.datasets_dir.glob("*"))
        for ds_dir in search_dirs:
            if not ds_dir.is_dir():
                continue
            for split in ["train", "val", "test"]:
                img_dir = ds_dir / "images" / split
                if img_dir.exists():
                    for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                        potential = img_dir / f"{image_id}{ext}"
                        if potential.exists():
                            img_path = potential
                            dataset_path = ds_dir
                            break
            if img_path:
                break

    if not img_path:
        raise HTTPException(status_code=404, detail="图片不存在")

    # 保存标注文件
    label_dir = dataset_path / "labels" / img_path.parent.name
    label_dir.mkdir(parents=True, exist_ok=True)
    label_path = label_dir / f"{img_path.stem}.txt"

    lines = []
    for box in boxes:
        cid = box.get("class_id", 0)
        bbox = box.get("bbox", [0, 0, 0, 0])
        lines.append(f"{cid} {' '.join(str(round(v, 6)) for v in bbox)}")

    label_path.write_text('\n'.join(lines))

    return {
        "success": True,
        "image_id": image_id,
        "boxes_saved": len(boxes),
        "message": f"已保存 {len(boxes)} 个标注"
    }
