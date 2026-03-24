"""
Tests for API routes
"""
import pytest
import json


class TestTasksAPI:
    """Test tasks API endpoints"""

    def test_create_task(self, db_session, test_dirs):
        """Test creating a new task via API"""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = response = client.post(
            "/api/tasks/",
            json={
                "name": "测试任务",
                "description": "检测图片中的车辆",
                "class_names": ["car", "truck"],
                "epochs": 50
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data

    def test_create_task_with_helmet_description(self, db_session, test_dirs):
        """Test that helmet-related description auto-fills class names"""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.post(
            "/api/tasks/",
            json={
                "name": "安全帽检测",
                "description": "检测未佩戴安全帽的人员"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Backend should auto-detect helmet classes
        assert "class_names" in data

    def test_list_tasks(self, db_session, test_dirs):
        """Test listing tasks"""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        # Create a task first
        client.post("/api/tasks/", json={"name": "任务1", "description": "test"})

        response = client.get("/api/tasks/")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data

    def test_get_nonexistent_task(self, db_session, test_dirs):
        """Test getting a task that doesn't exist"""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.get("/api/tasks/nonexistent_task_id")
        assert response.status_code == 404

    def test_get_task_logs(self, db_session, test_dirs):
        """Test getting task logs"""
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.core.database import TaskLog

        client = TestClient(app)

        # Create task and logs
        create_resp = client.post("/api/tasks/", json={"name": "日志测试"})
        task_id = create_resp.json()["task_id"]

        log = TaskLog(task_id=task_id, level="info", message="测试日志")
        db_session.add(log)
        db_session.commit()

        response = client.get(f"/api/tasks/{task_id}/logs")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert len(data["logs"]) >= 1


class TestModelsAPI:
    """Test models API endpoints"""

    def test_list_models_empty(self, db_session, test_dirs):
        """Test listing models when none exist"""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.get("/api/models/")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data

    def test_get_nonexistent_model(self, db_session, test_dirs):
        """Test getting a model that doesn't exist"""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.get("/api/models/nonexistent_task")
        assert response.status_code == 404


class TestDatasetsAPI:
    """Test datasets API endpoints"""

    def test_list_datasets(self, db_session, test_dirs):
        """Test listing datasets"""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.get("/api/datasets/all")
        assert response.status_code == 200
        data = response.json()
        assert "datasets" in data

    def test_get_demo_dataset(self, db_session, test_dirs):
        """Test getting demo dataset"""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.get("/api/datasets/demo")
        # May return 404 if demo doesn't exist, which is valid
        assert response.status_code in [200, 404]
