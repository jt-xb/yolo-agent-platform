# YOLO Agent 训推平台 - 需求文档

## 核心愿景

**输入**：一堆原始图片（或一段视频）  
**输出**：一个可直接部署在端侧的 YOLO 模型

整个训练过程由 Agent 全自动完成，无需人工干预调参。

---

## 完整流程

### 第一步：数据导入
- 用户上传图片压缩包或视频文件
- 如果是视频：用 OpenCV 按帧抽取图片

### 第二步：自动标注（Agent 调用 Grounding DINO + SAM）
- 用户提供类别名称，如 `["气瓶倒地", "未戴安全帽", "火灾"]`
- Grounding DINO 根据文本描述定位所有目标
- SAM 对每个候选框生成精确掩码
- 从掩码计算最小外接矩形 → YOLO 格式标注

### 第三步：Agent 自动训练
- Agent 启动 YOLO 训练（YOLOv8/v9/v10）
- 监控训练指标（loss、mAP、precision、recall）
- **如果指标不达标，Agent 自动调整超参数并重训**（最多迭代 N 轮）
- 超参数包括：学习率、batch size、图像增强策略、模型大小

### 第四步：模型导出
- 导出为 ONNX 格式（通用端侧格式）
- 也可以导出为 PyTorch、TFLite 等

### 第五步：推理部署
- 启动本地推理服务
- 上传图片测试效果
- 支持 API 调用（OpenAI 兼容格式）

---

## 用户交互界面

### 页面结构

1. **任务中心（Tasks）** — 查看当前训练任务状态
2. **数据集管理（Datasets）** — 上传/查看/标注数据
3. **模型中心（Models）** — 查看已训练模型，一键部署

### 用户操作流

```
进入页面 → 上传500张图片 + 输入类别名称
  → 点击"开始训练"
  → Agent 全自动跑：标注 → 训练 → 调参 → 训练 → ...
  → 训练完成 → 获得模型 → 一键部署
```

---

## 技术架构

### 后端模块

| 模块 | 职责 |
|------|------|
| `backend/main.py` | FastAPI 入口 |
| `backend/services/auto_labeling.py` | YOLO 自动标注（模拟） |
| `backend/services/grounding_dino_sam.py` | Grounding DINO + SAM 自动标注 |
| `backend/agents/trainer_agent.py` | 训练 Agent（调参 + 训练循环） |
| `backend/api/routes/` | API 路由 |

### 训练 Agent 逻辑

```
训练任务创建
    ↓
初始化参数（学习率=0.01, batch=16, 模型=yolov8n）
    ↓
执行 YOLO 训练（ultralytics）
    ↓
评估 mAP@0.5
    ↓
    ├─ mAP >= 目标阈值 → 保存模型 → 完成
    │
    └─ mAP < 目标阈值 → 调整超参数 → 重新训练
         （学习率↑/↓，batch调整，增强策略调整）
         （最多3-5次迭代）
```

---

## 已实现功能

- [x] 数据集管理页面（浏览、上传）
- [x] YOLO 格式支持（.txt 标注文件）
- [x] 合成数据集生成（40张图）
- [x] 自动标注 Tab（模拟视觉反馈）
- [x] 手动标注（SVG 画框）
- [x] 后端 API（训练、推理）
- [x] 前端 Proxy 配置（Vite → FastAPI）

## 待实现功能

- [ ] Grounding DINO + SAM 真实集成（模型加载问题）
- [ ] 训练 Agent 迭代循环（评估 → 调参 → 重训）
- [ ] 视频抽帧导入
- [ ] 模型导出（ONNX）
- [ ] 推理部署端点
- [ ] 增量训练支持

## 约束

- 纯离线可运行（除 LLM API 外）
- 支持 ARM64（Mac）、x86_64
- YOLO 输出格式：归一化坐标 `class_id x_center y_center width height`
- 端侧部署目标：ONNX / TFLite

---

## API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/datasets/demo` | 获取演示数据集 |
| POST | `/api/datasets/yolo-auto-label` | YOLO 自动标注 |
| POST | `/api/datasets/upload` | 上传图片 |
| POST | `/api/train` | 创建训练任务 |
| GET | `/api/train/{task_id}` | 查询训练状态 |
| POST | `/api/infer` | 推理 |
| GET | `/api/models` | 模型列表 |
