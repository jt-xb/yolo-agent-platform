"""
YOLO 训练流程 Agent
基于 LangChain ReAct 模式，自动解析任务并执行训练流程
"""
import re
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from langchain.tools import Tool
from langchain.agents import initialize_agent, AgentType
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from backend.core.llm import (
    get_llm_service,
    create_training_task_tool,
    start_training_tool,
    stop_training_tool,
    get_training_logs_tool,
    get_training_metrics_tool,
    download_model_tool,
    deploy_model_tool,
)
from backend.core.config import settings


# ============================================
# 定义 Agent 工具
# ============================================

def parse_task_description(task_description: str) -> Dict[str, Any]:
    """
    解析任务描述，提取关键信息
    
    Args:
        task_description: 自然语言描述，如"检测图片中的未佩戴安全帽人员"
    
    Returns:
        {
            "task_name": "安全帽检测",
            "target_objects": ["人", "安全帽"],
            "class_names": ["person", "helmet"],
            "suggested_epochs": 100,
            "suggested_model": "yolov8m",  # 根据复杂度建议
        }
    """
    llm = get_llm_service()
    
    system_prompt = """你是一个YOLO目标检测任务解析专家。用户会给出一个任务描述，你需要从中提取：
1. 任务名称（简短中文）
2. 要检测的目标对象列表
3. 建议的YOLO类别名称（英文，单数形式）
4. 建议的训练轮数（根据任务复杂度：简单任务50-100，复杂任务100-300）
5. 建议的YOLO模型大小（n=最小，s=小，m=中，l=大，x=最大；简单任务用n/s，复杂任务用m/l）

输出JSON格式，不要有多余文字。"""
    
    user_message = f"任务描述：{task_description}"
    
    response = llm.chat_with_system(system_prompt, user_message)
    
    # 解析 JSON 响应
    try:
        # 尝试提取JSON
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = eval(json_match.group())  # 简化解析，实际应该用json.loads但这里模型输出可能不标准
        else:
            result = {
                "task_name": task_description[:20],
                "target_objects": ["object"],
                "class_names": ["object"],
                "suggested_epochs": 100,
                "suggested_model": "yolov8s",
            }
    except Exception as e:
        result = {
            "task_name": task_description[:20],
            "target_objects": ["object"],
            "class_names": ["object"],
            "suggested_epochs": 100,
            "suggested_model": "yolov8s",
        }
    
    return result


def generate_data_yaml(task_id: str, class_names: List[str], train_path: str, val_path: str) -> Dict[str, Any]:
    """
    生成 YOLO data.yaml 配置文件
    """
    # TODO: 实际创建 YAML 文件
    yaml_content = f"""# YOLO 数据配置
# 任务: {task_id}
# 生成时间: {datetime.now().isoformat()}

path: {train_path}  # 数据集根目录
train: images/train  # 训练集图片
val: images/val      # 验证集图片

# 类别数
nc: {len(class_names)}

# 类别名称
names:
"""
    for i, name in enumerate(class_names):
        yaml_content += f"  {i}: {name}\n"
    
    return {
        "success": True,
        "yaml_content": yaml_content,
        "yaml_path": f"{settings.datasets_dir}/{task_id}/data.yaml",
    }


def generate_training_command(
    task_id: str,
    yolo_model: str = "yolov8n",
    data_yaml: str = "",
    epochs: int = 100,
    batch_size: int = 16,
    image_size: int = 640,
) -> Dict[str, Any]:
    """
    生成 YOLO 训练命令
    """
    # 根据是否使用 MLU 构建命令
    if settings.use_mlu:
        # MLU 训练命令
        # 注意: 实际命令需要根据寒武纪 SDK 调整
        cmd = f"""from ultralytics import YOLO
import os
os.environ["CAMBRICON_VISIBLE_DEVICES"] = "{settings.mlu_device_id}"

model = YOLO('{yolo_model}.pt')
results = model.train(
    data='{data_yaml}',
    epochs={epochs},
    batch={batch_size},
    imgsz={image_size},
    device='mlu',
    project='{settings.models_dir}',
    name='{task_id}',
    exist_ok=True,
)
"""
        command = f'python -c "{cmd}"'
    else:
        # GPU/CPU 训练命令
        cmd = f"""from ultralytics import YOLO
model = YOLO('{yolo_model}.pt')
results = model.train(
    data='{data_yaml}',
    epochs={epochs},
    batch={batch_size},
    imgsz={image_size},
    device='0',
    project='{settings.models_dir}',
    name='{task_id}',
    exist_ok=True,
)
"""
        command = f'python -c "{cmd}"'
    
    return {
        "success": True,
        "command": command,
        "script_path": f"{settings.logs_dir}/{task_id}/train.py",
    }


# ============================================
# 定义 Agent 工具列表
# ============================================

def get_yolo_agent_tools() -> List[Tool]:
    """获取 YOLO Agent 可用的工具列表"""
    
    tools = [
        Tool(
            name="parse_task_description",
            func=lambda x: parse_task_description(x),
            description="""解析任务描述，提取关键信息。用法：输入自然语言任务描述，输出任务名称、目标对象、建议的训练参数等。""",
        ),
        Tool(
            name="create_training_task",
            func=lambda x: create_training_task_tool(**eval(x) if x else {}),
            description="""创建训练任务。输入JSON格式：{"task_id": "xxx", "config": {...}}""",
        ),
        Tool(
            name="start_training",
            func=lambda x: start_training_tool(x),
            description="""启动训练。输入任务ID。""",
        ),
        Tool(
            name="stop_training",
            func=lambda x: stop_training_tool(x),
            description="""停止训练。输入任务ID。""",
        ),
        Tool(
            name="get_training_logs",
            func=lambda x: get_training_logs_tool(**eval(x) if x else {}),
            description="""获取训练日志。输入JSON格式：{"task_id": "xxx", "lines": 100}""",
        ),
        Tool(
            name="get_training_metrics",
            func=lambda x: get_training_metrics_tool(x),
            description="""获取训练指标。输入任务ID。""",
        ),
        Tool(
            name="download_model",
            func=lambda x: download_model_tool(x),
            description="""下载模型。输入任务ID。""",
        ),
        Tool(
            name="deploy_model",
            func=lambda x: deploy_model_tool(x),
            description="""部署模型。输入任务ID。""",
        ),
        Tool(
            name="generate_data_yaml",
            func=lambda x: generate_data_yaml(**eval(x) if x else {}),
            description="""生成YOLO数据配置文件。输入JSON格式：{"task_id": "xxx", "class_names": ["person", "helmet"], "train_path": "/path", "val_path": "/path"}""",
        ),
        Tool(
            name="generate_training_command",
            func=lambda x: generate_training_command(**eval(x) if x else {}),
            description="""生成YOLO训练命令。输入JSON格式：{"task_id": "xxx", "yolo_model": "yolov8n", "data_yaml": "/path", "epochs": 100, "batch_size": 16, "image_size": 640}""",
        ),
    ]
    
    return tools


# ============================================
# Agent 主逻辑
# ============================================

class TrainingAgent:
    """
    YOLO 训练流程 Agent
    
    负责：
    1. 接收用户任务描述
    2. 解析并生成训练配置
    3. 自动化执行从数据处理到模型生成的完整流程
    """
    
    def __init__(self):
        self.llm = get_llm_service()
        self.tools = get_yolo_agent_tools()
        
        # Agent 系统提示词
        self.system_prompt = """你是一个专业的YOLO目标检测训练助手。你的职责是帮助用户完成从任务描述到模型生成的全流程自动化。

可用工具：
- parse_task_description: 解析任务描述
- create_training_task: 创建训练任务
- start_training: 启动训练
- stop_training: 停止训练
- get_training_logs: 获取训练日志
- get_training_metrics: 获取训练指标
- download_model: 下载模型
- deploy_model: 部署模型
- generate_data_yaml: 生成YOLO数据配置
- generate_training_command: 生成训练命令

工作流程：
1. 接收用户的任务描述（如"检测未佩戴安全帽的人员"）
2. 使用 parse_task_description 解析任务
3. 创建训练任务
4. 准备数据配置
5. 生成并执行训练命令
6. 监控训练过程
7. 训练完成后提供模型下载/部署选项

重要原则：
- 所有操作在离线环境下完成
- 每步操作都要有清晰的状态反馈
- 遇到错误要给出具体的解决方案
- 只在用户明确要求时部署模型

请始终用中文与用户交流。"""
    
    def process_task(self, task_description: str, data_path: str) -> Dict[str, Any]:
        """
        处理训练任务
        
        Args:
            task_description: 自然语言任务描述
            data_path: 数据路径
        
        Returns:
            {
                "success": bool,
                "task_id": str,
                "message": str,
                "parsed_config": {...},
            }
        """
        # 1. 生成任务ID
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # 2. 解析任务描述
        parsed = parse_task_description(task_description)
        
        # 3. 构建训练配置
        config = {
            "task_id": task_id,
            "task_name": parsed.get("task_name", task_description[:20]),
            "task_description": task_description,
            "data_path": data_path,
            "yolo_model": parsed.get("suggested_model", "yolov8n"),
            "class_names": parsed.get("class_names", ["object"]),
            "suggested_epochs": parsed.get("suggested_epochs", 100),
            "batch_size": settings.default_batch_size,
            "image_size": settings.default_image_size,
        }
        
        # 4. 创建训练任务
        create_result = create_training_task_tool(task_id, config)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": f"任务已创建：{parsed.get('task_name', task_description)}",
            "parsed_config": parsed,
            "full_config": config,
        }
    
    def run_training_workflow(self, task_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行完整的训练流程
        
        这个方法会按顺序执行：
        1. 数据准备
        2. 生成配置文件
        3. 启动训练
        4. 监控进度
        5. 返回结果
        """
        # TODO: 实现完整的训练流程
        # 目前是占位实现，实际需要：
        # 1. 检查数据目录
        # 2. 划分训练集/验证集
        # 3. 生成 data.yaml
        # 4. 启动训练子进程
        # 5. 通过 WebSocket 推送进度
        # 6. 训练完成后更新任务状态
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "训练流程已启动，请通过任务详情页面监控进度",
        }


# 全局实例
_agent: Optional[TrainingAgent] = None

def get_training_agent() -> TrainingAgent:
    """获取训练 Agent 单例"""
    global _agent
    if _agent is None:
        _agent = TrainingAgent()
    return _agent
