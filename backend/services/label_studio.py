"""
Label Studio 集成服务
提供项目管理、图片导入、标注导出等完整集成功能
"""
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from backend.core.config import settings

__all__ = [
    "get_ls_client",
    "test_connection",
    "create_project",
    "get_or_create_project_for_dataset",
    "import_images_to_project",
    "sync_dataset_to_labelstudio",
    "export_project_annotations",
    "get_project_info",
]


class LabelStudioClient:
    """Label Studio API 客户端"""

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (base_url or os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")).rstrip("/")
        self.api_key = api_key or os.getenv("LABEL_STUDIO_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        })

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.session.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.session.post(f"{self.base_url}{path}", **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        return self.session.put(f"{self.base_url}{path}", **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self.session.delete(f"{self.base_url}{path}", **kwargs)

    def upload_file(self, path: str, file_data: bytes, filename: str) -> requests.Response:
        """上传文件到 Label Studio"""
        files = {"file": (filename, file_data)}
        return self.session.post(f"{self.base_url}{path}", files=files)


def get_ls_client(base_url: str = None, api_key: str = None) -> LabelStudioClient:
    """获取 LS 客户端实例"""
    return LabelStudioClient(base_url=base_url, api_key=api_key)


def test_connection(base_url: str = None, api_key: str = None) -> Dict[str, Any]:
    """
    测试 Label Studio 连接是否正常
    """
    client = get_ls_client(base_url, api_key)
    try:
        resp = client.get("/api/projects", timeout=10)
        if resp.status_code == 200:
            projects = resp.json()
            return {
                "success": True,
                "connected": True,
                "url": client.base_url,
                "project_count": len(projects) if isinstance(projects, list) else 0,
                "user": get_user_info(client),
            }
        elif resp.status_code == 401:
            return {"success": False, "error": "API Key 无效，请检查", "connected": False}
        else:
            return {"success": False, "error": f"HTTP {resp.status_code}", "connected": False}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "无法连接到 Label Studio，请确认服务已启动", "connected": False}
    except Exception as e:
        return {"success": False, "error": str(e), "connected": False}


def get_user_info(client: LabelStudioClient) -> Dict:
    """获取当前用户信息"""
    try:
        resp = client.get("/api/user", timeout=5)
        if resp.ok:
            return resp.json()
    except Exception:
        pass
    return {}


def get_projects(client: LabelStudioClient) -> List[Dict]:
    """获取所有项目"""
    resp = client.get("/api/projects")
    resp.raise_for_status()
    return resp.json()


def create_project(
    client: LabelStudioClient,
    name: str,
    description: str = "",
    label_config: str = None,
) -> Dict[str, Any]:
    """
    创建 Label Studio 项目

    Args:
        name: 项目名称
        description: 项目描述
        label_config: 标签配置 XML，如果不提供则使用默认 YOLO 模板

    Returns:
        {"success": True, "project": {...}}
    """
    # 默认 YOLO 标签配置
    if not label_config:
        label_config = """<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="labels">
    <Label value="object" background="blue"/>
  </RectangleLabels>
</View>"""

    payload = {
        "title": name,
        "description": description,
        "label_config": label_config,
        "expert_instruction": "请标注图片中的目标物体，用矩形框包围",
    }

    resp = client.post("/api/projects", json=payload, timeout=30)
    resp.raise_for_status()
    project = resp.json()

    return {"success": True, "project": project}


def create_yolo_label_config(class_names: List[str]) -> str:
    """
    根据类别列表生成 YOLO 格式的 Label Studio 标签配置

    Args:
        class_names: 类别列表，如 ["person", "helmet", "no_helmet"]

    Returns:
        Label Studio XML 配置字符串
    """
    label_lines = []
    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
        "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
    ]

    for i, name in enumerate(class_names):
        color = colors[i % len(colors)]
        label_lines.append(f'    <Label value="{name}" background="{color}"/>')

    labels_block = "\n".join(label_lines)

    config = f"""<View>
  <Header value="YOLO 目标检测标注 - {' / '.join(class_names)}"/>
  <Image name="image" value="$image" zoom="true"/>
  <PolygonLabels name="labels" toname="image">
{labels_block}
  </PolygonLabels>
  <RectangleLabels name="rect_labels" toname="image">
{labels_block}
  </RectangleLabels>
</View>"""
    return config


def get_or_create_project_for_dataset(
    client: LabelStudioClient,
    dataset_name: str,
    dataset_id: str,
    class_names: List[str] = None,
) -> Tuple[LabelStudioClient, int, str]:
    """
    获取或创建一个数据集对应的 Label Studio 项目

    Args:
        client: LS 客户端
        dataset_name: 数据集名称
        dataset_id: 平台数据集 ID
        class_names: 类别列表

    Returns:
        (client, project_id, project_url)
    """
    # 先查找同名项目
    projects = get_projects(client)
    project_id = None
    project_url = ""

    for p in projects:
        if p.get("name") == dataset_name:
            project_id = p["id"]
            break

    # 如果不存在则创建
    if not project_id:
        if class_names is None:
            class_names = ["object"]

        label_config = create_yolo_label_config(class_names)
        result = create_project(
            client,
            name=dataset_name,
            description=f"数据集 ID: {dataset_id} | 平台自动创建",
            label_config=label_config,
        )
        project = result["project"]
        project_id = project["id"]

    project_url = f"{client.base_url}/projects/{project_id}"

    return client, project_id, project_url


def import_images_to_project(
    client: LabelStudioClient,
    project_id: int,
    dataset_path: Path,
    split: str = "train",
) -> Dict[str, Any]:
    """
    将数据集中的图片批量导入到 Label Studio 项目

    Args:
        client: LS 客户端
        project_id: LS 项目 ID
        dataset_path: 数据集路径
        split: 数据集划分（train/val/test）

    Returns:
        {"success": True, "imported": N, "task_ids": [...]}
    """
    img_dir = dataset_path / "images" / split
    if not img_dir.exists():
        return {"success": False, "error": f"目录不存在: {img_dir}"}

    images = sorted([
        p for p in img_dir.glob("*")
        if p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
    ])

    if not images:
        return {"success": False, "error": f"没有找到图片: {img_dir}"}

    imported = 0
    task_ids = []
    failed = 0

    # Label Studio 接受两种导入方式：
    # 1. 直接上传文件（创建 task 并关联文件）
    # 2. 传入 URL 列表（需要可访问的 URL）
    # 这里用直接上传方式

    upload_resp = client.post(f"/api/projects/{project_id}/import", timeout=300)
    if upload_resp.status_code == 404:
        # 新版 LS 用不同的导入端点
        pass

    # 分批上传（LS 对大批量有处理）
    batch_size = 50
    for i in range(0, len(images), batch_size):
        batch = images[i:i + batch_size]

        # 准备文件列表
        files = {}
        for img_path in batch:
            with open(img_path, "rb") as f:
                files["files"] = (img_path.name, f.read(), f"image/{img_path.suffix.lstrip('.').replace('jpg','jpeg')}")

        try:
            resp = client.session.post(
                f"{client.base_url}/api/projects/{project_id}/import",
                files=files,
                timeout=120,
            )
            if resp.ok:
                result = resp.json() if resp.text else {}
                if isinstance(result, list):
                    task_ids.extend([t.get("id") for t in result if t.get("id")])
                imported += len(batch)
            else:
                failed += len(batch)
        except Exception as e:
            failed += len(batch)
            print(f"[LS Import] Batch failed: {e}")

    return {
        "success": True,
        "imported": imported,
        "total": len(images),
        "failed": failed,
        "task_ids": task_ids[:100],  # 限制返回数量
    }


def export_project_annotations(
    client: LabelStudioClient,
    project_id: int,
    output_dir: Path,
    format: str = "YOLO",
) -> Dict[str, Any]:
    """
    导出 Label Studio 项目的标注为 YOLO 格式

    Args:
        client: LS 客户端
        project_id: LS 项目 ID
        output_dir: 输出目录
        format: 导出格式（YOLO/COCO）

    Returns:
        {"success": True, "exported": N, "label_map": {...}}
    """
    output_dir = Path(output_dir)
    labels_dir = output_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    # 获取标签配置，构建 label_map
    label_map = {}
    try:
        cfg_resp = client.get(f"/api/projects/{project_id}/label_config")
        if cfg_resp.ok:
            config_text = cfg_resp.text
            # 解析 <Label value="xxx" .../>
            labels = re.findall(r'<Label\s+value="([^"]+)"', config_text)
            # 也尝试 PolygonLabels 格式
            labels += re.findall(r'<Label\s+object=\w+\s+value="([^"]+)"', config_text)
            labels = list(dict.fromkeys(labels))  # 去重保持顺序
            label_map = {name: idx for idx, name in enumerate(labels)}
    except Exception as e:
        print(f"[LS Export] Failed to get label config: {e}")

    # 获取项目任务
    tasks_resp = client.get(f"/api/projects/{project_id}/tasks", params={"limit": 10000})
    if not tasks_resp.ok:
        return {"success": False, "error": f"获取任务失败: {tasks_resp.status_code}"}

    tasks = tasks_resp.json()
    if isinstance(tasks, dict):
        tasks = tasks.get("results", [])

    exported = 0
    skipped = 0

    for task in tasks:
        task_id = task.get("id")
        # 获取该任务的标注
        ann_resp = client.get(f"/api/annotations", params={"task": task_id, "completed": True})
        annotations = ann_resp.json() if ann_resp.ok else []
        if isinstance(annotations, dict):
            annotations = annotations.get("results", [])

        if not annotations:
            skipped += 1
            continue

        # 解析标注结果
        yolo_lines = []
        for ann in annotations:
            result = ann.get("result", [])
            if not isinstance(result, list):
                result = []

            for item in result:
                item_type = item.get("type", "")
                if item_type not in ("rectangle",):
                    continue

                bbox = item.get("value", {})
                x = bbox.get("x", 0) / 100
                y = bbox.get("y", 0) / 100
                w = bbox.get("width", 0) / 100
                h = bbox.get("height", 0) / 100

                # 优先用 RectangleLabels
                labels_list = (
                    bbox.get("rectanglelabels", []) or
                    bbox.get("polygonlabels", []) or
                    bbox.get("labels", [])
                )
                if not labels_list:
                    continue
                label_name = labels_list[0]

                label_id = label_map.get(label_name, 0)
                cx = x + w / 2
                cy = y + h / 2
                yolo_lines.append(f"{label_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

        if yolo_lines:
            # 用 task_id 作为文件名避免中文问题
            label_path = labels_dir / f"task_{task_id}.txt"
            label_path.write_text("\n".join(yolo_lines))
            exported += 1

    return {
        "success": True,
        "exported": exported,
        "skipped": skipped,
        "total_tasks": len(tasks),
        "label_map": label_map,
        "output_dir": str(output_dir),
    }


def sync_dataset_to_labelstudio(
    dataset_id: str,
    dataset_path: Path,
    dataset_name: str,
    class_names: List[str],
    base_url: str = None,
    api_key: str = None,
    split: str = "train",
) -> Dict[str, Any]:
    """
    一键同步数据集到 Label Studio
    完整流程：连接测试 → 创建/查找项目 → 导入图片 → 返回打开链接

    Args:
        dataset_id: 平台数据集 ID
        dataset_path: 数据集路径
        dataset_name: 数据集名称
        class_names: 类别列表
        base_url: LS 地址
        api_key: LS API Key
        split: 导入哪个划分

    Returns:
        完整的同步结果，包含所有有用信息
    """
    client = get_ls_client(base_url, api_key)

    # Step 1: 测试连接
    conn = test_connection(base_url=base_url, api_key=api_key)
    if not conn.get("connected"):
        return {
            "success": False,
            "step": "connection",
            "error": conn.get("error", "连接失败"),
        }

    # Step 2: 获取或创建项目
    _, project_id, project_url = get_or_create_project_for_dataset(
        client, dataset_name, dataset_id, class_names
    )

    # Step 3: 导入图片
    import_result = import_images_to_project(client, project_id, dataset_path, split=split)

    # Step 4: 获取项目统计
    tasks_resp = client.get(f"/api/projects/{project_id}/tasks", params={"limit": 1})
    total_tasks = 0
    if tasks_resp.ok:
        data = tasks_resp.json()
        total_tasks = data.get("count", 0) if isinstance(data, dict) else len(data)

    return {
        "success": True,
        "step": "completed",
        "project_id": project_id,
        "project_url": project_url,
        "imported": import_result.get("imported", 0),
        "failed": import_result.get("failed", 0),
        "total_tasks": total_tasks,
        "label_studio_url": client.base_url,
        "open_url": project_url,
        "message": f"同步完成！已导入 {import_result.get('imported', 0)} 张图片到 Label Studio",
    }


def get_project_info(client: LabelStudioClient, project_id: int) -> Dict[str, Any]:
    """获取项目详细信息"""
    try:
        resp = client.get(f"/api/projects/{project_id}")
        resp.raise_for_status()
        project = resp.json()

        # 获取标注数量
        tasks_resp = client.get(f"/api/projects/{project_id}/tasks", params={"limit": 1})
        total_tasks = 0
        if tasks_resp.ok:
            data = tasks_resp.json()
            total_tasks = data.get("count", 0) if isinstance(data, dict) else len(data)

        # 获取已完成标注数
        from_label = project.get("labeling_count", 0) or 0

        return {
            "success": True,
            "project": {
                "id": project["id"],
                "name": project.get("title", ""),
                "description": project.get("description", ""),
                "total_tasks": total_tasks,
                "annotated_count": from_label,
                "created_at": project.get("created_at", ""),
                "url": f"{client.base_url}/projects/{project_id}",
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
