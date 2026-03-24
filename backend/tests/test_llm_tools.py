"""
Tests for LLM Agent tools
"""
import pytest
from datetime import datetime


class TestLLMTools:
    """Test the Agent tool functions"""

    def test_create_training_task_tool(self, db_session, test_dirs):
        """Test creating a training task via tool"""
        from backend.core.llm import create_training_task_tool

        config = {
            "task_name": "安全帽检测",
            "task_description": "检测未佩戴安全帽的人员",
            "yolo_model": "yolov8s",
            "epochs": 100,
            "batch_size": 16,
            "image_size": 640,
            "class_names": ["person", "helmet", "no_helmet"],
            "data_path": "/tmp/test_data",
        }

        result = create_training_task_tool("test_task_001", config)

        assert result["success"] is True
        assert result["task_id"] == "test_task_001"
        assert "安全帽检测" in result["message"] or "person" in result["message"]

    def test_create_training_task_tool_minimal(self, db_session, test_dirs):
        """Test creating task with minimal config"""
        from backend.core.llm import create_training_task_tool

        result = create_training_task_tool("test_task_002", {"task_name": "最小任务"})

        assert result["success"] is True
        assert result["task_id"] == "test_task_002"

    def test_get_training_logs_tool(self, db_session, test_dirs):
        """Test getting training logs"""
        from backend.core.llm import create_training_task_tool, get_training_logs_tool
        from backend.core.database import TaskLog

        # Create a task first
        task_id = "test_task_003"
        create_training_task_tool(task_id, {"task_name": "日志测试"})

        # Add some logs
        log = TaskLog(task_id=task_id, level="info", message="测试日志1")
        db_session.add(log)
        log2 = TaskLog(task_id=task_id, level="info", message="测试日志2")
        db_session.add(log2)
        db_session.commit()

        # Get logs
        result = get_training_logs_tool(task_id, lines=50)

        assert result["success"] is True
        assert result["total"] == 2
        assert len(result["logs"]) == 2

    def test_get_training_logs_tool_empty(self, db_session, test_dirs):
        """Test getting logs for non-existent task"""
        from backend.core.llm import get_training_logs_tool

        result = get_training_logs_tool("nonexistent_task")

        assert result["success"] is True
        assert result["total"] == 0
        assert result["logs"] == []

    def test_get_training_metrics_tool(self, db_session, test_dirs):
        """Test getting training metrics"""
        from backend.core.llm import create_training_task_tool, get_training_metrics_tool

        task_id = "test_task_004"
        create_training_task_tool(task_id, {"task_name": "指标测试"})

        result = get_training_metrics_tool(task_id)

        assert result["success"] is True
        assert "metrics" in result
        assert "status" in result["metrics"]

    def test_get_training_metrics_tool_nonexistent(self, db_session, test_dirs):
        """Test getting metrics for non-existent task"""
        from backend.core.llm import get_training_metrics_tool

        result = get_training_metrics_tool("nonexistent_task")

        assert result["success"] is False
        assert "metrics" in result

    def test_download_model_tool_no_model(self, db_session, test_dirs):
        """Test download tool when no model exists"""
        from backend.core.llm import download_model_tool

        result = download_model_tool("nonexistent_task")

        assert result["success"] is False
        assert "没有可下载" in result["message"]

    def test_download_model_tool_with_model(self, db_session, test_dirs):
        """Test download tool when model exists"""
        from backend.core.llm import download_model_tool
        from backend.core.database import GeneratedModel

        task_id = "test_task_005"

        # Create a model record
        model = GeneratedModel(
            task_id=task_id,
            name="测试模型",
            model_path="/tmp/test_models/test.pt",
            model_type="yolov8",
            file_size="25.6 MB",
        )
        db_session.add(model)
        db_session.commit()

        result = download_model_tool(task_id)

        assert result["success"] is True
        assert "download_url" in result
        assert result["file_size"] == "25.6 MB"

    def test_deploy_model_tool_no_model(self, db_session, test_dirs):
        """Test deploy tool when no model exists"""
        from backend.core.llm import deploy_model_tool

        result = deploy_model_tool("nonexistent_task")

        assert result["success"] is False
        assert "没有可部署" in result["message"]

    def test_deploy_model_tool_already_deployed(self, db_session, test_dirs):
        """Test deploy tool when model is already deployed"""
        from backend.core.llm import deploy_model_tool
        from backend.core.database import GeneratedModel
        from datetime import datetime

        task_id = "test_task_006"

        model = GeneratedModel(
            task_id=task_id,
            name="已部署模型",
            model_path="/tmp/test_models/test.pt",
            model_type="yolov8",
            is_deployed=True,
            deployed_at=datetime.utcnow(),
        )
        db_session.add(model)
        db_session.commit()

        result = deploy_model_tool(task_id)

        assert result["success"] is True
        assert "已经部署" in result["message"] or "endpoint" in result

    def test_stop_training_tool_nonexistent(self, db_session, test_dirs):
        """Test stop training for non-existent task"""
        from backend.core.llm import stop_training_tool

        result = stop_training_tool("nonexistent_task")

        assert result["success"] is False
        assert "不存在" in result["message"]


class TestLLMService:
    """Test LLM service wrapper"""

    def test_llm_service_initialization(self):
        """Test LLM service initializes correctly"""
        from backend.core.llm import LLMService

        service = LLMService()

        assert service.model_name == "deepseek-chat"
        assert service.api_base == "https://api.deepseek.com/v1"
        assert service._llm is None  # Lazy initialization
        assert service._llm_no_stream is None

    def test_convert_messages(self):
        """Test message conversion from dict to LangChain format"""
        from backend.core.llm import LLMService
        from langchain.schema import SystemMessage, HumanMessage, AIMessage

        service = LLMService()

        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]

        converted = service._convert_messages(messages)

        assert len(converted) == 4
        assert isinstance(converted[0], SystemMessage)
        assert isinstance(converted[1], HumanMessage)
        assert isinstance(converted[2], AIMessage)
        assert isinstance(converted[3], HumanMessage)
        assert converted[0].content == "You are a helpful assistant"

    def test_convert_messages_default_role(self):
        """Test message conversion with default role"""
        from backend.core.llm import LLMService
        from langchain.schema import HumanMessage

        service = LLMService()

        messages = [{"content": "Hello"}]
        converted = service._convert_messages(messages)

        assert len(converted) == 1
        assert isinstance(converted[0], HumanMessage)
