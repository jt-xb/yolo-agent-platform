"""
Tests for Agent Training Loop
"""
import pytest
import time


class TestAgentTrainingLoop:
    """Test the AgentTrainingLoop class"""

    def test_initialization(self, db_session, test_dirs):
        """Test training loop initializes correctly"""
        from backend.services.training_loop import AgentTrainingLoop

        loop = AgentTrainingLoop(
            task_id="test_loop_001",
            task_description="测试任务",
            class_names=["cat", "dog"]
        )

        assert loop.task_id == "test_loop_001"
        assert loop.task_description == "测试任务"
        assert loop.class_names == ["cat", "dog"]
        assert loop.status == "initializing"
        assert len(loop.iterations) == 0
        assert loop.best_metrics is None

    def test_generate_initial_config_small_classes(self, db_session, test_dirs):
        """Test initial config generation for few classes"""
        from backend.services.training_loop import AgentTrainingLoop

        loop = AgentTrainingLoop(
            task_id="test_loop_002",
            task_description="测试",
            class_names=["person"]  # <= 3 classes
        )

        config = loop.generate_initial_config()

        assert config["yolo_model"] == "yolov8s"
        assert config["epochs"] == 100
        assert config["batch_size"] == 16

    def test_generate_initial_config_medium_classes(self, db_session, test_dirs):
        """Test initial config generation for medium number of classes"""
        from backend.services.training_loop import AgentTrainingLoop

        loop = AgentTrainingLoop(
            task_id="test_loop_003",
            task_description="测试",
            class_names=["cat", "dog", "bird", "fish"]  # 4-10 classes
        )

        config = loop.generate_initial_config()

        assert config["yolo_model"] == "yolov8m"

    def test_generate_initial_config_many_classes(self, db_session, test_dirs):
        """Test initial config generation for many classes"""
        from backend.services.training_loop import AgentTrainingLoop

        loop = AgentTrainingLoop(
            task_id="test_loop_004",
            task_description="测试",
            class_names=["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10", "c11"]
        )

        config = loop.generate_initial_config()

        assert config["yolo_model"] == "yolov8l"

    def test_create_iteration(self, db_session, test_dirs):
        """Test creating a new iteration"""
        from backend.services.training_loop import AgentTrainingLoop

        loop = AgentTrainingLoop(
            task_id="test_loop_005",
            task_description="测试",
            class_names=["object"]
        )

        config = {"yolo_model": "yolov8n", "epochs": 50}
        iteration = loop._create_iteration(config)

        assert len(loop.iterations) == 1
        assert iteration.status == "running"
        assert iteration.config == config
        assert "test_loop_005_iter_1" in iteration.iteration_id

    def test_evaluate_and_decide_pass(self, db_session, test_dirs):
        """Test evaluation when metrics pass"""
        from backend.services.training_loop import AgentTrainingLoop, IterationDecision

        loop = AgentTrainingLoop(
            task_id="test_loop_006",
            task_description="测试",
            class_names=["object"]
        )

        # Create iteration with good metrics
        iteration = loop._create_iteration({"epochs": 50})
        iteration.map50 = 0.85
        iteration.map50_95 = 0.65
        iteration.precision = 0.80
        iteration.recall = 0.78

        decision = loop._evaluate_and_decide(iteration)

        assert decision == IterationDecision.PASS
        assert iteration.decision == IterationDecision.PASS
        assert "达标" in iteration.decision_reason

    def test_evaluate_and_decide_fail_retry(self, db_session, test_dirs):
        """Test evaluation when metrics fail but can retry"""
        from backend.services.training_loop import AgentTrainingLoop, IterationDecision

        loop = AgentTrainingLoop(
            task_id="test_loop_007",
            task_description="测试",
            class_names=["object"]
        )

        iteration = loop._create_iteration({"epochs": 50, "yolo_model": "yolov8n"})
        iteration.map50 = 0.50  # Below threshold
        iteration.map50_95 = 0.30
        iteration.precision = 0.50
        iteration.recall = 0.50

        decision = loop._evaluate_and_decide(iteration)

        assert decision == IterationDecision.FAIL_RETRY
        assert iteration.adjusted_config is not None
        assert iteration.adjusted_config["epochs"] > 50  # Should increase epochs

    def test_evaluate_and_decide_max_iteration(self, db_session, test_dirs):
        """Test evaluation when max iterations reached"""
        from backend.services.training_loop import AgentTrainingLoop, IterationDecision

        loop = AgentTrainingLoop(
            task_id="test_loop_008",
            task_description="测试",
            class_names=["object"]
        )
        loop.requirements.max_iterations = 2

        # Create 2 iterations
        for i in range(2):
            iteration = loop._create_iteration({"epochs": 50})
            iteration.map50 = 0.50
            iteration.map50_95 = 0.30
            iteration.precision = 0.50
            iteration.recall = 0.50

        # Third iteration should trigger max_iteration
        iteration = loop._create_iteration({"epochs": 50})
        iteration.map50 = 0.50
        iteration.map50_95 = 0.30
        iteration.precision = 0.50
        iteration.recall = 0.50

        decision = loop._evaluate_and_decide(iteration)

        assert decision == IterationDecision.MAX_ITERATION

    def test_build_final_result(self, db_session, test_dirs):
        """Test building final result"""
        from backend.services.training_loop import AgentTrainingLoop

        loop = AgentTrainingLoop(
            task_id="test_loop_009",
            task_description="测试",
            class_names=["object"]
        )

        # Create a completed iteration
        iteration = loop._create_iteration({"epochs": 50})
        iteration.map50 = 0.85
        iteration.map50_95 = 0.65
        iteration.precision = 0.80
        iteration.recall = 0.78
        iteration.status = "completed"

        loop.best_metrics = {"map50": 0.85, "map50_95": 0.65, "precision": 0.80, "recall": 0.78}
        loop.best_iteration_id = iteration.iteration_id
        loop.status = "completed"

        result = loop._build_final_result()

        assert result["task_id"] == "test_loop_009"
        assert result["status"] == "completed"
        assert result["total_iterations"] == 1
        assert result["best_metrics"]["map50"] == 0.85


class TestIterationDecision:
    """Test IterationDecision enum"""

    def test_iteration_decision_values(self):
        """Test decision enum values"""
        from backend.services.training_loop import IterationDecision

        assert IterationDecision.PASS.value == "pass"
        assert IterationDecision.FAIL_RETRY.value == "fail_retry"
        assert IterationDecision.FAIL_STOP.value == "fail_stop"
        assert IterationDecision.MAX_ITERATION.value == "max_iteration"


class TestTrainingIteration:
    """Test TrainingIteration dataclass"""

    def test_to_dict(self, db_session, test_dirs):
        """Test iteration serialization to dict"""
        from backend.services.training_loop import TrainingIteration

        iteration = TrainingIteration("iter_001", {"epochs": 100})
        iteration.map50 = 0.85
        iteration.map50_95 = 0.65
        iteration.status = "completed"

        d = iteration.to_dict()

        assert d["iteration_id"] == "iter_001"
        assert d["config"]["epochs"] == 100
        assert d["metrics"]["map50"] == 0.85
        assert d["status"] == "completed"


class TestGlobalLoopFunctions:
    """Test global loop management functions"""

    def test_start_and_get_agent_training_loop(self, db_session, test_dirs):
        """Test starting and retrieving a training loop"""
        from backend.services.training_loop import start_agent_training_loop, get_agent_training_loop

        loop = start_agent_training_loop(
            task_id="test_global_001",
            task_description="全局测试",
            class_names=["object"]
        )

        assert loop is not None
        assert loop.task_id == "test_global_001"

        # Retrieve it
        retrieved = get_agent_training_loop("test_global_001")
        assert retrieved is not None
        assert retrieved.task_id == "test_global_001"

    def test_get_nonexistent_loop(self, db_session, test_dirs):
        """Test retrieving non-existent loop"""
        from backend.services.training_loop import get_agent_training_loop

        result = get_agent_training_loop("nonexistent")
        assert result is None

    def test_stop_agent_training_loop(self, db_session, test_dirs):
        """Test stopping a training loop"""
        from backend.services.training_loop import (
            start_agent_training_loop,
            stop_agent_training_loop,
            get_agent_training_loop
        )

        loop = start_agent_training_loop(
            task_id="test_stop_001",
            task_description="停止测试",
            class_names=["object"]
        )

        assert get_agent_training_loop("test_stop_001") is not None

        result = stop_agent_training_loop("test_stop_001")
        assert result is True

        assert get_agent_training_loop("test_stop_001") is None

    def test_stop_nonexistent_loop(self, db_session, test_dirs):
        """Test stopping non-existent loop"""
        from backend.services.training_loop import stop_agent_training_loop

        result = stop_agent_training_loop("nonexistent")
        assert result is False
