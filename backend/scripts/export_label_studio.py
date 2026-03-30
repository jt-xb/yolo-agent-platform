"""
Label Studio 标注导出脚本
将 Label Studio 的标注导出为 YOLO 格式

Usage:
    python -m backend.scripts.export_label_studio \
        --project-id <project_id> \
        --output-dir <output_dir> \
        [--label-studio-url http://localhost:8080] \
        [--api-key <your_api_key>]
"""
import argparse
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


def get_label_studio_projects(base_url: str, api_key: str) -> List[Dict]:
    """获取 Label Studio 项目列表"""
    resp = requests.get(
        f"{base_url}/api/projects",
        headers={"Authorization": f"Token {api_key}"},
    )
    resp.raise_for_status()
    return resp.json()


def get_project_annotations(base_url: str, api_key: str, project_id: int) -> List[Dict]:
    """获取项目所有标注"""
    resp = requests.get(
        f"{base_url}/api/projects/{project_id}/annotations",
        headers={"Authorization": f"Token {api_key}"},
        params={"completed": True},
    )
    resp.raise_for_status()
    return resp.json()


def export_annotations(
    base_url: str,
    api_key: str,
    project_id: int,
    output_dir: Path,
    format: str = "YOLO",
) -> Dict[str, Any]:
    """
    导出项目标注为 YOLO 格式

    Label Studio 导出任务后会返回 JSON 格式，每个 task 包含 annotations。
    我们解析 annotations 中的 bboxes，转换为 YOLO 格式。
    """
    output_dir = Path(output_dir)
    images_dir = output_dir / "images"
    labels_dir = output_dir / "labels"

    for d in [images_dir, labels_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 获取 tasks
    resp = requests.get(
        f"{base_url}/api/projects/{project_id}/export",
        headers={"Authorization": f"Token {api_key}"},
        params={"format": format},
    )

    if resp.status_code == 404:
        # 尝试直接导出的备用方式
        resp = requests.post(
            f"{base_url}/api/projects/{project_id}/export",
            headers={"Authorization": f"Token {api_key}"},
            json={"format": format},
        )

    resp.raise_for_status()

    # 解析返回的标注数据
    tasks = resp.json()
    if isinstance(tasks, str):
        # 如果返回的是文件路径/URL，下载它
        tasks = []

    # 如果是直接导出为 JSON，tasks 是列表
    if not isinstance(tasks, list):
        tasks = []

    # 获取 label-to-id 映射
    label_map_resp = requests.get(
        f"{base_url}/api/projects/{project_id}",
        headers={"Authorization": f"Token {api_key}"},
    )
    label_map = {}
    if label_map_resp.ok:
        project = label_map_resp.json()
        label_map_resp = requests.get(
            f"{base_url}/api/projects/{project_id}/label_config",
            headers={"Authorization": f"Token {api_key}"},
        )
        if label_map_resp.ok:
            config = label_map_resp.text
            # 简单解析 <Label value="person" .../>
            import re
            labels = re.findall(r'value="([^"]+)"', config)
            label_map = {name: idx for idx, name in enumerate(labels)}

    exported = 0
    errors = 0

    for task in tasks:
        task_id = task.get("id", "unknown")
        annotations = task.get("annotations", [])

        # 获取图片信息
        image_filename = task.get("data", {}).get("image", "")
        if not image_filename:
            image_filename = task.get("file_upload", "")
        if not image_filename:
            continue

        # 下载图片（如果需要）
        if image_filename.startswith("http"):
            img_resp = requests.get(image_filename)
            img_resp.raise_for_status()
            img_data = img_resp.content
            img_name = Path(image_filename).name
        else:
            img_resp = requests.get(
                f"{base_url}/data/{image_filename}",
                headers={"Authorization": f"Token {api_key}"},
            )
            if img_resp.ok:
                img_data = img_resp.content
                img_name = Path(image_filename).name
            else:
                errors += 1
                continue

        # 保存图片
        img_path = images_dir / img_name
        with open(img_path, "wb") as f:
            f.write(img_data)

        # 解析标注
        label_lines = []
        for ann in annotations:
            result = ann.get("result", [])
            if not isinstance(result, list):
                result = []

            for item in result:
                # item 类型：rectangle / ellipse / polygon
                item_type = item.get("type", "")
                if item_type not in ("rectangle",):
                    continue

                # 坐标
                bbox = item.get("value", {})
                x = bbox.get("x", 0) / 100  # 归一化
                y = bbox.get("y", 0) / 100
                w = bbox.get("width", 0) / 100
                h = bbox.get("height", 0) / 100

                # 类别
                labels_list = bbox.get("rectanglelabels", []) or bbox.get("labels", [])
                if not labels_list:
                    continue
                label_name = labels_list[0]

                label_id = label_map.get(label_name, 0)

                # YOLO 格式: class_id cx cy w h（归一化）
                cx = x + w / 2
                cy = y + h / 2
                label_lines.append(f"{label_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

        # 保存标签文件
        label_name = Path(img_name).with_suffix(".txt")
        label_path = labels_dir / label_name
        with open(label_path, "w") as f:
            f.write("\n".join(label_lines))

        exported += 1

    return {
        "success": True,
        "exported": exported,
        "errors": errors,
        "output_dir": str(output_dir),
        "label_map": label_map,
    }


def main():
    parser = argparse.ArgumentParser(description="导出 Label Studio 标注为 YOLO 格式")
    parser.add_argument("--project-id", type=int, required=True, help="Label Studio 项目 ID")
    parser.add_argument("--output-dir", type=str, required=True, help="输出目录")
    parser.add_argument("--label-studio-url", type=str, default="http://localhost:8080", help="Label Studio 地址")
    parser.add_argument("--api-key", type=str, default=os.getenv("LABEL_STUDIO_API_KEY", ""), help="Label Studio API Key")
    parser.add_argument("--format", type=str, default="YOLO", help="导出格式")

    args = parser.parse_args()

    if not args.api_key:
        print("警告：未提供 API Key，尝试无认证访问（可能受限）")

    print(f"正在导出项目 {args.project_id} 到 {args.output_dir} ...")
    result = export_annotations(
        base_url=args.label_studio_url,
        api_key=args.api_key,
        project_id=args.project_id,
        output_dir=Path(args.output_dir),
        format=args.format,
    )

    print(f"导出完成！")
    print(f"  导出图片: {result['exported']}")
    print(f"  错误: {result['errors']}")
    print(f"  输出目录: {result['output_dir']}")
    print(f"  类别映射: {result['label_map']}")


if __name__ == "__main__":
    main()
