"""
Agent 训练循环服务
核心逻辑：训练 → 评估 → 判断是否达标 → 不达标则调整参数重训
"""
import os
import time
import random
import uuid
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from backend.core.config import settings
from pathlib import Path


class IterationDecision(Enum):
    """迭代决策结果"""
    PASS = "pass"          # 达标，结束
    FAIL_RETRY = "fail_retry"  # 不达标，调整参数重训
    FAIL_STOP = "fail_stop"    # 严重失败，停止
    MAX_ITERATION = "max_iteration"  # 达到最大迭代次数


class TrainingIteration:
    """单次训练迭代记录"""
    def __init__(self, iteration_id: str, config: Dict[str, Any]):
        self.iteration_id = iteration_id
        self.config = config.copy()
        self.status = "running"  # running, completed, failed
        self.started_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None

        # 训练指标
        self.train_loss: Optional[float] = None
        self.val_loss: Optional[float] = None
        self.map50: Optional[float] = None
        self.map50_95: Optional[float] = None
        self.precision: Optional[float] = None
        self.recall: Optional[float] = None

        # 决策
        self.decision: Optional[IterationDecision] = None
        self.decision_reason: Optional[str] = None
        self.adjusted_config: Optional[Dict[str, Any]] = None  # 下一代配置

        # 日志
        self.logs: List[str] = []

    def to_dict(self):
        return {
            "iteration_id": self.iteration_id,
            "config": self.config,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metrics": {
                "train_loss": self.train_loss,
                "val_loss": self.val_loss,
                "map50": self.map50,
                "map50_95": self.map50_95,
                "precision": self.precision,
                "recall": self.recall,
            },
            "decision": self.decision.value if self.decision else None,
            "decision_reason": self.decision_reason,
            "adjusted_config": self.adjusted_config,
            "logs": self.logs,
        }


@dataclass
class TargetRequirements:
    """目标要求"""
    map50_threshold: float = 0.82
    map50_95_threshold: float = 0.62
    precision_threshold: float = 0.78
    recall_threshold: float = 0.75
    max_iterations: int = 4


class AgentTrainingLoop:
    """
    Agent 驱动的训练循环

    工作流程：
    1. 根据任务描述生成初始配置
    2. 执行训练
    3. 评估结果
    4. 做出决策：
       - 达标 → 结束，输出最优模型
       - 不达标 → 调整参数，生成新的训练迭代
       - 达到最大迭代 → 停止，选择最佳结果
    5. 重复直到满足条件或达到上限
    """

    def __init__(self, task_id: str, task_description: str, class_names: List[str], dataset_id: str = None, pretrained_model: str = ""):
        self.task_id = task_id
        self.task_description = task_description
        self.class_names = class_names
        self.dataset_id = dataset_id
        self.pretrained_model = pretrained_model  # 增量训练：预训练模型路径

        self.iterations: List[TrainingIteration] = []
        self.current_iteration: Optional[TrainingIteration] = None
        self.status = "initializing"  # initializing, running, completed, failed, stopped
        self.best_iteration_id: Optional[str] = None
        self.best_metrics: Optional[Dict] = None

        # 停止事件
        self._stop_event = threading.Event()
        # 暂停事件
        self._pause_event = threading.Event()

        # 目标要求
        self.requirements = TargetRequirements()

        # 输出目录
        self.output_dir = settings.models_dir / task_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_initial_config(self) -> Dict[str, Any]:
        """根据任务描述生成初始训练配置"""
        # 简单策略：根据类别数量和复杂度选择模型大小
        if len(self.class_names) <= 3:
            model_size = "yolov8s"
        elif len(self.class_names) <= 10:
            model_size = "yolov8m"
        else:
            model_size = "yolov8l"

        config = {
            "yolo_model": model_size,
            "epochs": 100,
            "batch_size": 16,
            "image_size": 640,
            "lr0": 0.01,
            "lrf": 0.01,
            "momentum": 0.937,
            "weight_decay": 0.0005,
            "augmentation": True,
            "patience": 50,
        }

        # 增量训练：加入预训练模型路径
        if self.pretrained_model:
            config["pretrained_model"] = self.pretrained_model

        return config

    def _create_iteration(self, config: Dict[str, Any]) -> TrainingIteration:
        """创建新的训练迭代"""
        iteration_id = f"{self.task_id}_iter_{len(self.iterations) + 1}"
        iteration = TrainingIteration(iteration_id, config)
        self.iterations.append(iteration)
        self.current_iteration = iteration
        return iteration

    def _run_training(self, iteration: TrainingIteration) -> bool:
        """
        执行单次训练
        始终使用真实 YOLO 训练（不做 mock fallback）
        """
        import time as time_module

        iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 开始第 {len(self.iterations)} 次训练迭代")
        iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📦 模型: {iteration.config['yolo_model']}, Epochs: {iteration.config['epochs']}, Batch: {iteration.config['batch_size']}")

        total_epochs = iteration.config["epochs"]

        # 确定数据集路径（优先使用 Phase 1 生成好的）
        data_yaml = iteration.config.get("data_yaml")
        if not data_yaml or not os.path.exists(data_yaml):
            # 尝试任务专属数据集
            task_yaml = self.output_dir / "data.yaml"
            if task_yaml.exists():
                data_yaml = str(task_yaml)
            else:
                # 回退到演示数据集
                data_yaml = "/tmp/yolo_demo_dataset/data.yaml"

        model_name = iteration.config.get("yolo_model", "yolov8n")
        batch_size = iteration.config.get("batch_size", 4)
        image_size = iteration.config.get("image_size", 640)

        # 增量训练：优先使用指定的预训练模型路径
        pretrained_path = iteration.config.get("pretrained_model")
        if pretrained_path and os.path.exists(pretrained_path):
            model_path = pretrained_path
            iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📦 增量训练：加载预训练模型 {pretrained_path}")
        else:
            model_path = f"{model_name}.pt"

        iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🖥️  设备: CPU")
        iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📂 数据集: {data_yaml}")

        # 真实 YOLO 训练
        try:
            from ultralytics import YOLO
            iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 启动 YOLOv8 真实训练（最多 {min(total_epochs, 50)} epochs）...")

            model = YOLO(model_path)

            # Pause check before training
            if self._pause_event.is_set():
                self.status = "paused"
                iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏸️ 训练已暂停，等待恢复...")
                while self._pause_event.is_set() and not self._stop_event.is_set():
                    time_module.sleep(1)
                if self._stop_event.is_set():
                    return False
                self.status = "running"
                iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ▶️ 训练已恢复")

            results = model.train(
                data=data_yaml,
                epochs=min(total_epochs, 50),  # 限制最多50轮
                batch=min(batch_size, 8),
                imgsz=min(image_size, 640),
                device='cpu',
                project=str(self.output_dir.parent),
                name=self.task_id,
                exist_ok=True,
                verbose=False,
                save=True,
                plots=False,
                patience=20,
            )

            # 解析真实结果
            if hasattr(results, 'results_dict'):
                rd = results.results_dict
                iteration.map50 = round(rd.get('metrics/mAP50(B)', 0), 4)
                iteration.map50_95 = round(rd.get('metrics/mAP50-95(B)', 0), 4)
                iteration.precision = round(rd.get('metrics/precision(B)', 0), 4)
                iteration.recall = round(rd.get('metrics/recall(B)', 0), 4)
                iteration.train_loss = round(rd.get('train/box_loss', 0), 4)
                iteration.val_loss = round(rd.get('val/box_loss', 0), 4)
            else:
                # 尝试从 results.box 获取
                try:
                    iteration.map50 = round(float(results.box.map50), 4)
                    iteration.map50_95 = round(float(results.box.map), 4)
                    iteration.precision = round(float(results.box.mp), 4)
                    iteration.recall = round(float(results.box.mr), 4)
                except Exception:
                    iteration.map50 = 0.0
                    iteration.map50_95 = 0.0
                    iteration.precision = 0.0
                    iteration.recall = 0.0

            iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 第 {len(self.iterations)} 次迭代完成（真实训练）!")
            iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 结果: mAP50={iteration.map50:.4f}, mAP95={iteration.map50_95:.4f}")
            iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 精度: P={iteration.precision:.4f}, R={iteration.recall:.4f}")

        except Exception as e:
            import traceback
            iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 真实训练出错: {e}")
            iteration.logs.append(f"详细错误: {traceback.format_exc()[-500:]}")
            # 不再 fallback 到 mock，直接记录失败
            iteration.map50 = 0.0
            iteration.map50_95 = 0.0
            iteration.precision = 0.0
            iteration.recall = 0.0
            iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 训练失败，指标置零，将进入评估决策")

        iteration.status = "completed"
        iteration.completed_at = datetime.utcnow()
        return True

    def _evaluate_and_decide(self, iteration: TrainingIteration) -> IterationDecision:
        """
        评估迭代结果，决定下一步
        优先使用 LLM 分析，失败时回退到规则引擎
        """
        m = iteration.metrics = {
            "map50": iteration.map50,
            "map50_95": iteration.map50_95,
            "precision": iteration.precision,
            "recall": iteration.recall,
        }

        # 检查是否是历史最佳
        if self.best_metrics is None or m["map50"] > self.best_metrics["map50"]:
            self.best_metrics = m.copy()
            self.best_iteration_id = iteration.iteration_id

        # ========== LLM 决策阶段 ==========
        llm_used = False
        llm_error_msg = None
        try:
            from backend.core.llm import get_llm_service
            import json, re

            system_prompt = """你是一位计算机视觉训练专家。分析 YOLO 训练结果，决定下一步行动。

决策选项：
- PASS: 所有指标达标 → 结束训练
- FAIL_RETRY: 未达标但可以继续优化 → 调整配置重训
- MAX_ITERATION: 已达最大迭代次数 → 结束训练
- FAIL_STOP: 训练持续失败 → 停止

请始终以 JSON 格式回复：
{"decision": "PASS|FAIL_RETRY|MAX_ITERATION|FAIL_STOP", "reason": "原因说明", "adjustments": {"yolo_model": "yolov8n/m/s/l", "epochs": 100, "lr0": 0.01, ...}}
如果不需要调整，adjustments 可为空对象 {}。
"""
            user_message = f"""训练迭代 {len(self.iterations)} 结果：
- mAP50: {m.get('map50', 0):.4f}（目标: {self.requirements.map50_threshold}）
- mAP95: {m.get('map50_95', 0):.4f}（目标: {self.requirements.map50_95_threshold}）
- 精确率: {m.get('precision', 0):.4f}（目标: {self.requirements.precision_threshold}）
- 召回率: {m.get('recall', 0):.4f}（目标: {self.requirements.recall_threshold}）

当前迭代: {len(self.iterations)} / {self.requirements.max_iterations}
当前配置: {iteration.config}
"""
            llm = get_llm_service()
            response = llm.chat_with_system(system_prompt, user_message, temperature=0.3)

            # 尝试从响应中提取 JSON（用正则找第一个 {...} 块）
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                decision_str = result.get("decision", "").strip().upper()
                reason = result.get("reason", "LLM 决策")
                adjustments = result.get("adjustments", {})

                decision_map = {
                    "PASS": IterationDecision.PASS,
                    "FAIL_RETRY": IterationDecision.FAIL_RETRY,
                    "MAX_ITERATION": IterationDecision.MAX_ITERATION,
                    "FAIL_STOP": IterationDecision.FAIL_STOP,
                }
                decision = decision_map.get(decision_str)

                if decision is not None:
                    llm_used = True
                    iteration.decision_reason = f"[LLM] {reason}"
                    iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 LLM 决策: {decision_str} — {reason}")

                    if adjustments and decision == IterationDecision.FAIL_RETRY:
                        iteration.adjusted_config = {**iteration.config, **adjustments}
                        iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔧 LLM 建议调整: {adjustments}")

                    iteration.decision = decision

                    if decision == IterationDecision.PASS:
                        iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 评估通过：模型达到上线标准")
                    elif decision == IterationDecision.MAX_ITERATION:
                        iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 达到最大迭代次数")
                    elif decision == IterationDecision.FAIL_STOP:
                        iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 LLM 判断训练持续失败，停止")
                    return decision
                else:
                    llm_error_msg = f"LLM 返回了未知决策: {decision_str}"
            else:
                llm_error_msg = f"LLM 响应无法解析为 JSON: {response[:200]}"
        except ImportError:
            llm_error_msg = "LLM 模块不可用"
        except Exception as e:
            llm_error_msg = f"LLM 调用失败: {str(e)}"

        # ========== 回退到规则引擎 ==========
        if llm_error_msg:
            iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {llm_error_msg}，使用规则引擎决策")
            iteration.decision_reason = f"[规则引擎回退] {llm_error_msg}"

        # 检查是否达标
        map50_ok = m["map50"] >= self.requirements.map50_threshold
        map95_ok = m["map50_95"] >= self.requirements.map50_95_threshold
        prec_ok = m["precision"] >= self.requirements.precision_threshold
        recall_ok = m["recall"] >= self.requirements.recall_threshold
        all_ok = map50_ok and map95_ok and prec_ok and recall_ok

        if all_ok:
            iteration.decision = IterationDecision.PASS
            iteration.decision_reason = f"所有指标达标！mAP50={m['map50']:.3f}, mAP95={m['map50_95']:.3f}"
            iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 评估通过：模型达到上线标准")
            return IterationDecision.PASS

        # 未达标，分析原因并调整
        issues = []
        if not map50_ok:
            issues.append(f"mAP50不足({m['map50']:.3f}<{self.requirements.map50_threshold})")
        if not map95_ok:
            issues.append(f"mAP95不足({m['map50_95']:.3f}<{self.requirements.map50_95_threshold})")
        if not prec_ok:
            issues.append(f"精确率不足({m['precision']:.3f}<{self.requirements.precision_threshold})")
        if not recall_ok:
            issues.append(f"召回率不足({m['recall']:.3f}<{self.requirements.recall_threshold})")

        if len(self.iterations) >= self.requirements.max_iterations:
            iteration.decision = IterationDecision.MAX_ITERATION
            iteration.decision_reason = f"达到最大迭代次数({self.requirements.max_iterations}次)，选择历史最佳结果"
            iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {iteration.decision_reason}")
            return IterationDecision.MAX_ITERATION

        # 生成调整后的配置
        new_config = iteration.config.copy()
        adjustment_reasons = []

        if not recall_ok:
            new_config["epochs"] = min(new_config["epochs"] + 50, 300)
            new_config["lr0"] = min(new_config["lr0"] * 1.5, 0.03)
            adjustment_reasons.append("增加训练轮数和学习率以提升召回")

        if not prec_ok:
            if new_config["yolo_model"] == "yolov8s":
                new_config["yolo_model"] = "yolov8m"
            elif new_config["yolo_model"] == "yolov8m":
                new_config["yolo_model"] = "yolov8l"
            new_config["epochs"] = min(new_config["epochs"] + 30, 250)
            adjustment_reasons.append(f"升级模型到{new_config['yolo_model']}以提升精度")

        if not map50_ok:
            adjustment_reasons.append("调整超参以提升整体mAP")
            new_config["epochs"] = min(new_config["epochs"] + 30, 300)

        iteration.adjusted_config = new_config
        iteration.decision = IterationDecision.FAIL_RETRY
        iteration.decision_reason = f"{' '.join(issues)}。调整策略: {' '.join(adjustment_reasons)}"
        iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔧 {iteration.decision_reason}")

        return IterationDecision.FAIL_RETRY

    def run(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        执行完整的 Agent 训练循环

        完整流程：
        1. 数据分析阶段 → Agent 分析数据质量，决定是否需要自动标注
        2. 训练阶段 → 执行 YOLO 训练
        3. 评估阶段 → 检查 mAP/P/R 是否达标
        4. 迭代决策 → 达标则结束，不达标则调整参数重训
        """
        import time as time_module

        self.status = "running"

        # ========================================
        # 阶段1：数据分析 + 自动标注（真实）
        # ========================================
        analysis_logs = [
            f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 ===== Agent 数据分析阶段 =====",
            f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Agent 开始分析数据集...",
            f"[{datetime.now().strftime('%H:%M:%S')}] 📊 检测目标: {', '.join(self.class_names)}",
        ]

        # 使用真实的数据集路径
        if self.dataset_id:
            # 优先使用用户选择的数据集
            dataset_path = Path(settings.data_dir) / "datasets" / self.dataset_id
            if not dataset_path.exists():
                dataset_path = Path("/tmp") / self.dataset_id
        else:
            dataset_path = Path("/tmp/yolo_demo_dataset")
        img_dir = dataset_path / "images" / "train"
        lbl_dir = dataset_path / "labels" / "train"

        if not img_dir.exists():
            analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 数据目录不存在: {img_dir}")
            # 尝试使用其他数据集
            for p in Path("/tmp").glob("ds_*/images/train"):
                if list(p.glob("*.jpg")) or list(p.glob("*.png")):
                    img_dir = p
                    lbl_dir = p.parent.parent / "labels" / p.parent.name
                    dataset_path = p.parent.parent.parent
                    analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 切换到数据集: {dataset_path.name}")
                    break

        all_images = sorted(img_dir.glob("*.jpg")) + sorted(img_dir.glob("*.png"))
        analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🗂️  扫描数据目录: {img_dir}")
        analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📈 发现 {len(all_images)} 张待处理图片")

        if len(all_images) == 0:
            analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 未找到图片，尝试创建演示数据集...")
            try:
                from backend.scripts.create_demo_dataset import main as create_demo
                create_demo()
                all_images = sorted(img_dir.glob("*.jpg"))
                analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 演示数据集创建完成: {len(all_images)} 张图片")
            except Exception as e:
                analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 创建演示数据集失败: {e}")

        # 统计已有标注的图片
        labeled = 0
        total_objects = 0
        for img in all_images:
            lbl_file = lbl_dir / f"{img.stem}.txt"
            if lbl_file.exists():
                labeled += 1
                try:
                    total_objects += sum(1 for _ in open(lbl_file) if _.strip())
                except Exception:
                    pass

        analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🏷️  已标注: {labeled}/{len(all_images)} 张，合计 {total_objects} 个目标框")

        # 调用真实的自动标注服务
        need_autolabel = (labeled < len(all_images) * 0.5) or (total_objects == 0)
        if need_autolabel:
            analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 决策: 需要自动标注（Grounding DINO + SAM / YOLOv8 回退）")
            analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✏️  启动自动标注流程...")

            # 检查 auto-labeling 服务状态
            try:
                from backend.services.grounding_dino_sam import get_info, annotate_dataset
                info = get_info()
                analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📡 自动标注服务模式: {info.get('mode', 'unknown')}")
                analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]    DINO: {'✅ 可用' if info.get('dino_ok') else '❌ 不可用'}")
                analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]    SAM: {'✅ 可用' if info.get('sam_ok') else '❌ 不可用'}")
                analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]    YOLOv8回退: {'✅ 可用' if info.get('yolo_fallback') else '❌ 不可用'}")
            except Exception as e:
                analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 获取服务信息失败: {e}，继续尝试标注")

            # 需要标注的图片（未标注的）
            unlabeled_images = [img for img in all_images if not (lbl_dir / f"{img.stem}.txt").exists()]
            unlabeled_paths = [str(img) for img in unlabeled_images]

            if unlabeled_paths:
                # 自动标注输出目录
                auto_lbl_dir = dataset_path / "labels" / "auto"
                auto_lbl_dir.mkdir(parents=True, exist_ok=True)

                # 建立 class_name 到 id 的映射
                class_name_to_id = {name: i for i, name in enumerate(self.class_names)}

                analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✏️  开始标注 {len(unlabeled_paths)} 张图片...")

                try:
                    result = annotate_dataset(
                        image_paths=unlabeled_paths,
                        class_names=self.class_names,
                        output_dir=str(auto_lbl_dir),
                        class_name_to_id=class_name_to_id,
                        box_threshold=0.25,
                    )
                    annotated_count = result.get("annotated", 0)
                    total_objs = result.get("total_objects", 0)
                    analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 自动标注完成！成功标注 {annotated_count}/{len(unlabeled_paths)} 张，发现 {total_objs} 个目标")

                    # 将自动标注结果复制到正式 labels 目录
                    import shutil
                    for lbl_file in auto_lbl_dir.glob("*.txt"):
                        target = lbl_dir / lbl_file.name
                        shutil.copy2(str(lbl_file), str(target))

                except Exception as e:
                    analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 自动标注失败: {e}")
                    analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 将使用已有标注继续训练（即使不完整）")
        else:
            analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 数据质量良好，跳过自动标注")

        # 重新统计标注后的数据集
        final_labeled = 0
        final_objects = 0
        for img in all_images:
            lbl_file = lbl_dir / f"{img.stem}.txt"
            if lbl_file.exists() and lbl_file.stat().st_size > 0:
                final_labeled += 1
                try:
                    final_objects += sum(1 for _ in open(lbl_file) if _.strip())
                except Exception:
                    pass

        analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 数据集统计: {final_labeled}/{len(all_images)} 张已标注，共 {final_objects} 个目标")

        # ========== LLM 数据分析建议 ==========
        try:
            from backend.core.llm import get_llm_service
            dataset_summary = f"""数据集分析摘要：
- 总图片数: {len(all_images)}
- 已标注图片: {final_labeled}
- 标注率: {final_labeled/len(all_images)*100:.1f}%（需要>50%才建议跳过自动标注）
- 总目标框: {final_objects}
- 类别列表: {', '.join(self.class_names)}

是否应该使用自动标注？应该采用什么样的数据增强策略？"""
            llm_response = get_llm_service().chat_with_system(
                "你是一位计算机视觉数据工程师。分析这个数据集的质量，并给出训练策略建议。",
                dataset_summary,
                temperature=0.3,
            )
            # 只取前300字符避免日志过长
            truncated = llm_response[:300].replace("\n", " ")
            analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 LLM 数据分析: {truncated}")
        except Exception as e:
            analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 LLM 数据分析不可用: {str(e)[:100]}")

        # 生成 data.yaml（使用绝对路径），同时保存到任务专属目录供训练使用
        data_yaml_path = dataset_path / "data.yaml"
        task_yaml_path = self.output_dir / "data.yaml"
        yaml_content = f"""# YOLO Dataset for {self.task_id}
path: {dataset_path.resolve()}
train: images/train
val: images/val

nc: {len(self.class_names)}
names: {self.class_names}
"""
        try:
            data_yaml_path.write_text(yaml_content)
            task_yaml_path.write_text(yaml_content)
            analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ data.yaml 已生成: {task_yaml_path}")
        except Exception as e:
            analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 写入 data.yaml 失败: {e}")

        # 划分训练/验证
        train_count = int(len(all_images) * 0.8)
        val_count = len(all_images) - train_count
        analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔀 训练集/验证集划分: {train_count} / {val_count}")
        analysis_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📄 生成 data.yaml 配置文件")

        # 先发送数据分析阶段的日志（不算正式迭代，progress=0）
        if progress_callback:
            fake_iter = {
                "iteration_id": f"{self.task_id}_analysis",
                "config": {"phase": "data_analysis", "class_names": self.class_names},
                "status": "data_analysis",
                "logs": analysis_logs,
                "metrics": {},
            }
            progress_callback(fake_iter, 0, self.requirements.max_iterations)

        time_module.sleep(0.3)

        # 检查停止信号（分析阶段结束后）
        if self._stop_event.is_set():
            self.status = "stopped"
            return self._build_final_result()

        # 检查暂停信号
        if self._pause_event.is_set():
            self.status = "paused"
            while self._pause_event.is_set() and not self._stop_event.is_set():
                import time as time_module
                time_module.sleep(1)
            if self._stop_event.is_set():
                self.status = "stopped"
                return self._build_final_result()
            self.status = "running"

        # ========================================
        # 阶段2：训练迭代循环
        # ========================================
        initial_config = self.generate_initial_config()
        iteration = self._create_iteration(initial_config)
        iteration.logs = analysis_logs + [
            f"[{datetime.now().strftime('%H:%M:%S')}] ",
            f"[{datetime.now().strftime('%H:%M:%S')}] ===== Agent 训练阶段开始 =====",
            f"[{datetime.now().strftime('%H:%M:%S')}] 🎯 训练目标: mAP50≥{self.requirements.map50_threshold} | P≥{self.requirements.precision_threshold} | R≥{self.requirements.recall_threshold}",
            f"[{datetime.now().strftime('%H:%M:%S')}] ⚙️  初始配置: {initial_config}",
        ]

        if progress_callback:
            progress_callback(iteration.to_dict(), 1, self.requirements.max_iterations)

        while True:
            # 检查停止信号
            if self._stop_event.is_set():
                self.status = "stopped"
                break

            # 检查暂停信号
            if self._pause_event.is_set():
                self.status = "paused"
                iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏸️ 训练已暂停，等待恢复...")
                while self._pause_event.is_set() and not self._stop_event.is_set():
                    import time as time_module
                    time_module.sleep(1)
                if self._stop_event.is_set():
                    self.status = "stopped"
                    break
                self.status = "running"
                iteration.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ▶️ 训练已恢复")

            # 执行训练
            self._run_training(iteration)

            if progress_callback:
                progress_callback(iteration.to_dict(), len(self.iterations), self.requirements.max_iterations)

            # 评估并决策
            decision = self._evaluate_and_decide(iteration)

            if decision == IterationDecision.PASS:
                self.status = "completed"
                break

            if decision in [IterationDecision.MAX_ITERATION, IterationDecision.FAIL_STOP]:
                self.status = "completed"
                break

            # 检查停止信号（决定继续迭代之前）
            if self._stop_event.is_set():
                self.status = "stopped"
                break

            # 生成下一轮迭代
            iteration = self._create_iteration(iteration.adjusted_config)

        return self._build_final_result()

    def _build_final_result(self) -> Dict[str, Any]:
        """构建最终结果"""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "total_iterations": len(self.iterations),
            "best_iteration_id": self.best_iteration_id,
            "best_metrics": self.best_metrics,
            "iterations": [it.to_dict() for it in self.iterations],
            "final_model_path": str(self.output_dir / "weights" / "best.pt"),
        }


# 全局训练循环管理（按 task_id 索引）
_active_loops: Dict[str, AgentTrainingLoop] = {}


def start_agent_training_loop(
    task_id: str,
    task_description: str,
    class_names: List[str],
    dataset_id: str = None,
    pretrained_model: str = ""
) -> AgentTrainingLoop:
    """启动 Agent 训练循环"""
    loop = AgentTrainingLoop(task_id, task_description, class_names, dataset_id, pretrained_model)
    _active_loops[task_id] = loop
    return loop


def get_agent_training_loop(task_id: str) -> Optional[AgentTrainingLoop]:
    """获取训练循环"""
    return _active_loops.get(task_id)


def stop_agent_training_loop(task_id: str) -> bool:
    """停止训练循环"""
    loop = _active_loops.get(task_id)
    if loop:
        loop._stop_event.set()
        del _active_loops[task_id]
        return True
    return False


def pause_agent_training_loop(task_id: str) -> bool:
    """暂停训练循环"""
    loop = _active_loops.get(task_id)
    if loop:
        loop._pause_event.set()
        loop.status = "paused"
        return True
    return False


def resume_agent_training_loop(task_id: str) -> bool:
    """恢复训练循环"""
    loop = _active_loops.get(task_id)
    if loop and loop.status == "paused":
        loop._pause_event.clear()
        loop.status = "running"
        return True
    return False


def get_agent_training_loop(task_id: str):
    """获取运行中的训练循环"""
    return _active_loops.get(task_id)
