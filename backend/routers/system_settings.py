"""
系统设置 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.core.database import get_db, LLMConfig
from backend.core.config import settings

router = APIRouter(prefix="/api/settings", tags=["系统设置"])


class LLMConfigIn(BaseModel):
    api_key: str = ""
    api_base: str = ""
    model: str = ""
    enabled: bool = True


@router.get("/llm")
def get_llm_config(db: Session = Depends(get_db)):
    """获取 LLM 配置"""
    cfg = db.query(LLMConfig).first()
    if not cfg:
        # 没有数据库配置时，从环境变量返回
        return {
            "api_key": settings.llm_api_key or "",
            "api_base": settings.llm_api_base or "",
            "model": settings.llm_model or "",
            "enabled": bool(settings.llm_api_key),
            "source": "env",
        }
    return {
        "api_key": cfg.api_key or "",
        "api_base": cfg.api_base or "",
        "model": cfg.model or "",
        "enabled": cfg.enabled,
        "source": "db",
    }


@router.put("/llm")
def save_llm_config(body: LLMConfigIn, db: Session = Depends(get_db)):
    """保存 LLM 配置"""
    cfg = db.query(LLMConfig).first()
    if not cfg:
        cfg = LLMConfig()
        db.add(cfg)

    cfg.api_key = body.api_key
    cfg.api_base = body.api_base
    cfg.model = body.model
    cfg.enabled = body.enabled
    db.commit()

    # 实时更新 settings 运行时值（仅内存生效，重启后以数据库为准）
    settings.llm_api_key = body.api_key
    settings.llm_api_base = body.api_base
    settings.llm_model = body.model

    return {"success": True, "message": "LLM 配置已保存"}


@router.post("/llm/test")
def test_llm_connection(body: LLMConfigIn, db: Session = Depends(get_db)):
    """测试 LLM 连接"""
    try:
        from backend.core.llm import LLMService

        # 临时创建一个测试用的 LLMService
        class _TmpLLM:
            def __init__(self, api_key, api_base, model):
                self.api_key = api_key
                self.api_base = api_base
                self.model = model

        # 直接用 requests 测试
        import requests
        headers = {"Authorization": f"Bearer {body.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": body.model or "deepseek-chat",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }
        resp = requests.post(
            f"{body.api_base}/chat/completions",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            return {"success": True, "message": "连接成功"}
        else:
            return {"success": False, "message": f"错误: {resp.status_code} {resp.text[:200]}"}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)}"}
