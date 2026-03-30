"""
Label Studio 集成 API 路由
提供与 Label Studio 的无缝集成功能
"""
import os
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from backend.core.config import settings
from backend.services.label_studio import (
    get_ls_client,
    test_connection,
    create_project,
    create_yolo_label_config,
    get_or_create_project_for_dataset,
    import_images_to_project,
    sync_dataset_to_labelstudio,
    export_project_annotations,
    get_project_info,
)

router = APIRouter(prefix="/api/label-studio", tags=["Label Studio 集成"])


class LSSettings(BaseModel):
    url: str = "http://localhost:8080"
    api_key: str = ""


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    class_names: List[str] = ["object"]


class SyncDatasetRequest(BaseModel):
    dataset_id: str
    dataset_name: str = ""
    class_names: List[str] = ["object"]
    split: str = "train"
    url: str = "http://localhost:8080"
    api_key: str = ""


class ExportAnnotationsRequest(BaseModel):
    project_id: int
    output_dir: str = ""
    format: str = "YOLO"
    url: str = "http://localhost:8080"
    api_key: str = ""


# ============================================
# 连接与状态
# ============================================

@router.post("/connect")
def ls_connect(settings_req: LSSettings = Body(...)):
    """
    测试 Label Studio 连接

    请求体:
    {
        "url": "http://localhost:8080",
        "api_key": "your_api_key"
    }
    """
    result = test_connection(
        base_url=settings_req.url,
        api_key=settings_req.api_key,
    )
    return result


@router.get("/status")
def ls_status():
    """
    获取 Label Studio 连接状态（使用环境变量中的配置）
    """
    url = os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")
    api_key = os.getenv("LABEL_STUDIO_API_KEY", "")
    result = test_connection(base_url=url, api_key=api_key)
    return {
        "configured": bool(url and api_key),
        "url": url,
        **result,
    }


# ============================================
# 项目管理
# ============================================

@router.get("/projects")
def ls_list_projects():
    """
    获取 Label Studio 所有项目列表
    """
    url = os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")
    api_key = os.getenv("LABEL_STUDIO_API_KEY", "")

    result = test_connection(base_url=url, api_key=api_key)
    if not result.get("connected"):
        return {
            "success": False,
            "error": result.get("error", "连接失败"),
            "projects": [],
        }

    client = get_ls_client(base_url=url, api_key=api_key)
    projects = client.get("/api/projects").json()

    # 格式化返回
    formatted = []
    for p in (projects if isinstance(projects, list) else []):
        formatted.append({
            "id": p.get("id"),
            "name": p.get("title", ""),
            "description": p.get("description", ""),
            "url": f"{url}/projects/{p.get('id')}",
            "created_at": p.get("created_at", ""),
        })

    return {"success": True, "projects": formatted}


@router.post("/projects")
def ls_create_project(req: CreateProjectRequest = Body(...)):
    """
    在 Label Studio 中创建新项目

    请求体:
    {
        "name": "安全帽检测数据集",
        "description": "用于安全帽检测的标注项目",
        "class_names": ["person", "helmet", "no_helmet"]
    }
    """
    url = os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")
    api_key = os.getenv("LABEL_STUDIO_API_KEY", "")

    conn = test_connection(base_url=url, api_key=api_key)
    if not conn.get("connected"):
        return {
            "success": False,
            "error": conn.get("error", "连接失败，请检查 Label Studio 服务和 API Key"),
        }

    client = get_ls_client(base_url=url, api_key=api_key)
    label_config = create_yolo_label_config(req.class_names)

    result = create_project(
        client,
        name=req.name,
        description=req.description,
        label_config=label_config,
    )

    if result["success"]:
        project = result["project"]
        return {
            "success": True,
            "message": f"项目 '{req.name}' 创建成功",
            "project": {
                "id": project["id"],
                "name": project["title"],
                "url": f"{url}/projects/{project['id']}",
                "open_url": f"{url}/projects/{project['id']}/datasets",
            },
            "class_names": req.class_names,
        }

    return {"success": False, "error": "创建失败"}


@router.get("/projects/{project_id}")
def ls_get_project(project_id: int):
    """获取指定项目的详细信息"""
    url = os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")
    api_key = os.getenv("LABEL_STUDIO_API_KEY", "")

    client = get_ls_client(base_url=url, api_key=api_key)
    result = get_project_info(client, project_id)
    return result


# ============================================
# 同步与导入
# ============================================

@router.post("/sync-dataset")
def ls_sync_dataset(req: SyncDatasetRequest = Body(...)):
    """
    一键同步数据集到 Label Studio

    完整流程：
    1. 测试连接
    2. 创建或查找已有项目（以数据集名称）
    3. 导入图片到项目
    4. 返回打开链接

    请求体:
    {
        "dataset_id": "ds_xxx",
        "dataset_name": "安全帽数据集",
        "class_names": ["person", "helmet", "no_helmet"],
        "split": "train",
        "url": "http://localhost:8080",
        "api_key": "your_api_key"
    }
    """
    # 解析数据集路径
    if req.dataset_id == "demo":
        dataset_path = Path("/tmp/yolo_demo_dataset")
    else:
        dataset_path = Path(f"/tmp/{req.dataset_id}")

    if not dataset_path.exists():
        return {"success": False, "error": f"数据集不存在: {req.dataset_id}"}

    result = sync_dataset_to_labelstudio(
        dataset_id=req.dataset_id,
        dataset_path=dataset_path,
        dataset_name=req.dataset_name or req.dataset_id,
        class_names=req.class_names,
        base_url=req.url,
        api_key=req.api_key,
        split=req.split,
    )

    return result


@router.post("/projects/{project_id}/import")
def ls_import_images(project_id: int):
    """
    将数据集图片导入到已存在的 LS 项目

    注意：此接口需要通过 FormData 传递 dataset_id 参数
    """
    return {"success": False, "message": "请使用 /sync-dataset 接口一键同步"}


@router.post("/projects/{project_id}/export")
def ls_export_annotations(
    project_id: int,
    req: ExportAnnotationsRequest = Body(...),
):
    """
    导出 Label Studio 项目的标注

    请求体:
    {
        "project_id": 1,
        "output_dir": "/tmp/ls_export",
        "format": "YOLO",
        "url": "http://localhost:8080",
        "api_key": "your_api_key"
    }
    """
    output_dir = Path(req.output_dir) if req.output_dir else Path(f"/tmp/ls_export_{project_id}")

    client = get_ls_client(base_url=req.url, api_key=req.api_key)
    result = export_project_annotations(
        client=client,
        project_id=project_id,
        output_dir=output_dir,
        format=req.format,
    )

    if result["success"]:
        return {
            **result,
            "download_url": f"/api/label-studio/download-export/{project_id}",
            "message": f"导出完成！共 {result['exported']} 个标注文件",
        }

    return result


@router.get("/download-export/{project_id}")
def ls_download_export(project_id: int, format: str = "zip"):
    """
    下载导出的标注文件（ZIP 格式）
    """
    export_dir = Path(f"/tmp/ls_export_{project_id}")
    if not export_dir.exists():
        raise HTTPException(status_code=404, detail="导出文件不存在，请先导出")

    import zipfile
    zip_path = Path(f"/tmp/ls_export_{project_id}.zip")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for label_file in export_dir.rglob("*.txt"):
            zf.write(label_file, label_file.relative_to(export_dir))

    from fastapi.responses import FileResponse
    return FileResponse(
        str(zip_path),
        media_type="application/zip",
        filename=f"yolo_labels_{project_id}.zip",
    )


# ============================================
# 一键打开标注
# ============================================

@router.get("/open/{project_id}")
def ls_open_project(project_id: int):
    """
    获取直接打开 Label Studio 项目的 URL
    """
    url = os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")
    return {
        "success": True,
        "open_url": f"{url}/projects/{project_id}/datamanager",
        "annotate_url": f"{url}/projects/{project_id}/tasks",
    }
