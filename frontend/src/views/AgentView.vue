<template>
  <div class="agent-view">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="section-title">🤖 Agent 智能训练</h2>
        <span class="header-subtitle" v-if="currentTask">任务: {{ currentTask.name }}</span>
      </div>
      <div class="header-actions">
        <el-tag v-if="currentTask?.status" :type="statusType" size="small">
          {{ statusText }}
        </el-tag>
        <el-button
          v-if="!currentTask || currentTask?.status === 'pending' || currentTask?.status === 'stopped'"
          type="primary"
          @click="startAgentTraining"
          :loading="starting"
        >
          🚀 开始 Agent 训练
        </el-button>
        <el-button
          v-if="currentTask?.status === 'training'"
          type="warning"
          @click="pauseTraining"
        >
          ⏸️ 暂停
        </el-button>
        <el-button
          v-if="currentTask?.status === 'paused'"
          type="success"
          @click="resumeTraining"
        >
          ▶️ 恢复
        </el-button>
        <el-button
          v-if="currentTask?.status === 'training' || currentTask?.status === 'paused'"
          type="danger"
          @click="stopTraining"
        >
          ⏹️ 停止
        </el-button>
      </div>
    </div>

    <!-- Main Content: Left (Dataset) + Right (Agent Panel) -->
    <div class="agent-layout">
      <!-- Left Panel: Dataset Info -->
      <div class="left-panel">
        <div class="panel-section">
          <h3 class="panel-title">📁 选择数据集</h3>
          <el-select v-model="selectedDatasetId" style="width: 100%" @change="onDatasetChange">
            <el-option
              v-for="ds in datasets"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </div>

        <!-- Dataset Stats -->
        <div class="panel-section" v-if="datasetStats">
          <h3 class="panel-title">📊 数据集统计</h3>
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-num">{{ datasetStats.total_images }}</span>
              <span class="stat-label">总图片</span>
            </div>
            <div class="stat-card">
              <span class="stat-num">{{ datasetStats.annotated }}</span>
              <span class="stat-label">已标注</span>
            </div>
            <div class="stat-card">
              <span class="stat-num">{{ datasetStats.unannotated }}</span>
              <span class="stat-label">未标注</span>
            </div>
            <div class="stat-card">
              <span class="stat-num">{{ datasetStats.annotation_rate }}%</span>
              <span class="stat-label">标注率</span>
            </div>
          </div>

          <!-- Progress Bar -->
          <div class="annotation-progress">
            <el-progress
              :percentage="datasetStats.annotation_rate"
              :stroke-width="12"
              :color="progressColor"
            />
          </div>
        </div>

        <!-- Class Names -->
        <div class="panel-section" v-if="classNames.length">
          <h3 class="panel-title">🏷️ 检测类别</h3>
          <div class="class-tags">
            <el-tag v-for="c in classNames" :key="c" size="small" type="primary">
              {{ c }}
            </el-tag>
          </div>
        </div>

        <!-- Image Preview -->
        <div class="panel-section" v-if="previewImages.length">
          <h3 class="panel-title">🖼️ 图片预览</h3>
          <div class="image-grid">
            <div v-for="img in previewImages" :key="img" class="image-item">
              <img :src="img" alt="preview" @error="handleImgError" />
            </div>
          </div>
        </div>

        <!-- Training Config -->
        <div class="panel-section">
          <h3 class="panel-title">⚙️ 训练配置</h3>
          <el-form label-position="top" size="small">
            <el-form-item label="模型大小">
              <el-select v-model="config.yolo_model" style="width: 100%">
                <el-option label="YOLOv8n (最小)" value="yolov8n" />
                <el-option label="YOLOv8s (小)" value="yolov8s" />
                <el-option label="YOLOv8m (中)" value="yolov8m" />
                <el-option label="YOLOv8l (大)" value="yolov8l" />
              </el-select>
            </el-form-item>
            <el-form-item label="最大迭代次数">
              <el-input-number v-model="config.max_iterations" :min="1" :max="10" style="width: 100%" />
            </el-form-item>
            <el-form-item label="目标 mAP@50">
              <el-slider v-model="config.target_map50" :min="0.5" :max="0.99" :step="0.01" show-input />
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- Right Panel: Agent Suggestions & Actions -->
      <div class="right-panel">
        <!-- Current Phase Indicator -->
        <div class="phase-indicator">
          <div class="phase-badge" :class="'phase-' + currentPhase">
            <span class="phase-icon">{{ phaseIcon }}</span>
            <span class="phase-text">{{ phaseText }}</span>
          </div>
        </div>

        <!-- Agent Suggestion Card -->
        <div class="agent-suggestion-card" v-if="agentSuggestion">
          <div class="suggestion-header">
            <span class="suggestion-icon">🤖</span>
            <span class="suggestion-title">Agent 分析建议</span>
          </div>
          <div class="suggestion-content">
            <p class="suggestion-text">{{ agentSuggestion }}</p>
          </div>
          <div class="suggestion-action" v-if="agentOptions.length">
            <div class="action-label">建议操作：</div>
            <div class="action-options">
              <div
                v-for="opt in agentOptions"
                :key="opt.value"
                class="action-option"
                :class="{ selected: selectedOption === opt.value }"
                @click="selectedOption = opt.value"
              >
                <span class="option-label">{{ opt.label }}</span>
                <span class="option-desc">{{ opt.desc }}</span>
              </div>
            </div>
            <el-button
              type="primary"
              @click="confirmAgentAction"
              :disabled="!selectedOption"
              style="margin-top: 16px; width: 100%"
            >
              确认执行
            </el-button>
          </div>
        </div>

        <!-- Training Metrics (during training) -->
        <div class="training-metrics" v-if="currentTask?.status === 'training' || currentTask?.status === 'paused'">
          <h3 class="panel-title">📈 当前训练指标</h3>
          <div class="metrics-grid">
            <div class="metric-item">
              <span class="metric-label">Epoch</span>
              <span class="metric-value">{{ currentMetrics.epoch || 0 }} / {{ currentMetrics.total || config.max_iterations }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">mAP@50</span>
              <span class="metric-value" :class="mapClass(currentMetrics.map50)">
                {{ currentMetrics.map50 ? (currentMetrics.map50 * 100).toFixed(2) + '%' : '-' }}
              </span>
            </div>
            <div class="metric-item">
              <span class="metric-label">mAP</span>
              <span class="metric-value">
                {{ currentMetrics.map50_95 ? (currentMetrics.map50_95 * 100).toFixed(2) + '%' : '-' }}
              </span>
            </div>
            <div class="metric-item">
              <span class="metric-label">Loss</span>
              <span class="metric-value">
                {{ currentMetrics.loss ? currentMetrics.loss.toFixed(4) : '-' }}
              </span>
            </div>
          </div>
          <el-progress
            v-if="currentTask?.progress"
            :percentage="Math.round(currentTask.progress)"
            :stroke-width="10"
            style="margin-top: 12px"
          />
        </div>

        <!-- Iteration History -->
        <div class="iteration-history" v-if="iterations.length">
          <h3 class="panel-title">📜 迭代历史</h3>
          <div class="iteration-list">
            <div v-for="iter in iterations" :key="iter.iteration" class="iteration-item">
              <div class="iter-header">
                <span class="iter-badge">迭代 {{ iter.iteration }}</span>
                <span class="iter-decision" :class="'decision-' + iter.decision">
                  {{ decisionLabel(iter.decision) }}
                </span>
              </div>
              <div class="iter-stats">
                <span>mAP50: {{ iter.metrics?.map50 ? (iter.metrics.map50 * 100).toFixed(1) + '%' : '-' }}</span>
                <span>模型: {{ iter.yolo_model || '-' }}</span>
                <span>Epochs: {{ iter.epochs || '-' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Real-time Logs -->
        <div class="log-panel">
          <div class="log-header">
            <h3 class="panel-title">📋 训练日志</h3>
            <el-button size="small" text @click="clearLogs">清空</el-button>
          </div>
          <div class="log-container" ref="logContainer">
            <div
              v-for="(log, i) in logs"
              :key="i"
              class="log-line"
              :class="'log-' + log.level"
            >
              <span class="log-time">{{ formatTime(log.timestamp) }}</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getDatasets } from '../api/datasets'
import {
  createTask,
  startTask,
  stopTask,
  pauseTask,
  resumeTask,
  getTask,
  getTaskLogs,
  getTaskIterations,
  submitDecision,
  getPendingDecision,
  createTaskStream,
} from '../api/tasks'

const route = useRoute()
const router = useRouter()

// State
const datasets = ref([])
const selectedDatasetId = ref('')
const currentTask = ref(null)
const starting = ref(false)
const logs = ref([])
const iterations = ref([])
const agentSuggestion = ref('')
const agentOptions = ref([])
const selectedOption = ref('')
const currentMetrics = ref({})
const eventSource = ref(null)
const logContainer = ref(null)

// Config
const config = ref({
  yolo_model: 'yolov8n',
  max_iterations: 4,
  target_map50: 0.85,
})

// Dataset stats
const datasetStats = ref(null)
const classNames = ref([])
const previewImages = ref([])

// Computed
const currentPhase = computed(() => {
  if (!currentTask.value) return 'idle'
  return currentTask.value.status || 'idle'
})

const statusType = computed(() => {
  const s = currentTask.value?.status
  if (s === 'training') return 'success'
  if (s === 'paused') return 'warning'
  if (s === 'completed') return 'primary'
  if (s === 'failed') return 'danger'
  return 'info'
})

const statusText = computed(() => {
  const s = currentTask.value?.status
  if (s === 'training') return '训练中'
  if (s === 'paused') return '已暂停'
  if (s === 'completed') return '已完成'
  if (s === 'failed') return '失败'
  if (s === 'pending') return '等待中'
  return '未知'
})

const phaseIcon = computed(() => {
  const p = currentPhase.value
  if (p === 'training') return '🔥'
  if (p === 'paused') return '⏸️'
  if (p === 'completed') return '✅'
  if (p === 'failed') return '❌'
  return '⏳'
})

const phaseText = computed(() => {
  const p = currentPhase.value
  if (p === 'training') return 'Agent 正在分析数据集...'
  if (p === 'paused') return '训练已暂停'
  if (p === 'completed') return '训练完成！'
  if (p === 'failed') return '训练失败'
  return '等待开始'
})

const progressColor = computed(() => {
  const rate = datasetStats.value?.annotation_rate || 0
  if (rate >= 80) return '#67c23a'
  if (rate >= 50) return '#e6a23c'
  return '#f56c6c'
})

// Methods
async function loadDatasets() {
  try {
    const data = await getDatasets()
    datasets.value = data.datasets || []
    if (datasets.value.length && !selectedDatasetId.value) {
      selectedDatasetId.value = datasets.value[0].id
      await onDatasetChange()
    }
  } catch (e) {
    console.error('loadDatasets error:', e)
  }
}

async function onDatasetChange() {
  const ds = datasets.value.find(d => d.id === selectedDatasetId.value)
  if (ds) {
    datasetStats.value = {
      total_images: ds.total_images || 0,
      annotated: ds.annotated || 0,
      unannotated: ds.unannotated || (ds.total_images || 0) - (ds.annotated || 0),
      annotation_rate: ds.annotation_rate || 0,
    }
    classNames.value = ds.class_names || []
    previewImages.value = (ds.preview_images || []).slice(0, 6)
  }
}

function handleImgError(e) {
  e.target.style.display = 'none'
}

function formatTime(ts) {
  if (!ts) return ''
  if (typeof ts === 'string' && ts.length >= 8) {
    const match = ts.match(/T(\d{2}:\d{2}:\d{2})/) || ts.match(/^(\d{2}:\d{2}:\d{2})/)
    if (match) return match[1]
  }
  return ts
}

function mapClass(val) {
  if (!val) return ''
  return val >= 0.82 ? 'metric-good' : 'metric-bad'
}

function decisionLabel(decision) {
  const labels = {
    pass: '✅ 达标',
    fail_retry: '🔄 调整重试',
    fail_stop: '❌ 失败停止',
    max_iteration: '⏹️ 达到上限',
    user_decision: '👤 用户决策',
  }
  return labels[decision] || decision || '-'
}

async function startAgentTraining() {
  if (!selectedDatasetId.value) {
    ElMessage.warning('请先选择数据集')
    return
  }

  starting.value = true
  try {
    // 创建任务
    const taskData = {
      name: `Agent训练_${Date.now()}`,
      description: 'Agent 智能训练任务',
      dataset_id: selectedDatasetId.value,
      yolo_model: config.value.yolo_model,
      epochs: 50,
      batch_size: 16,
      training_type: 'agent',
      class_names: classNames.value,
    }
    const result = await createTask(taskData)
    currentTask.value = { task_id: result.task_id, status: 'pending', name: taskData.name }
    logs.value = []
    iterations.value = []
    agentSuggestion.value = ''
    agentOptions.value = []

    // 启动训练
    await startTask(result.task_id)
    currentTask.value.status = 'training'
    logs.value.push({ level: 'info', message: '🚀 Agent 训练已启动', timestamp: new Date().toISOString() })

    // 连接 SSE 流
    connectSSE(result.task_id)
  } catch (e) {
    ElMessage.error('启动失败: ' + e.message)
  } finally {
    starting.value = false
  }
}

function connectSSE(taskId) {
  if (eventSource.value) {
    eventSource.value.close()
  }

  const es = createTaskStream(taskId, {
    onMessage(data) {
      handleSSEMessage(data)
    },
    onError(err) {
      console.error('SSE error:', err)
      logs.value.push({ level: 'error', message: '连接断开: ' + err, timestamp: new Date().toISOString() })
    },
    onEnd() {
      console.log('SSE stream ended')
    },
  })
  eventSource.value = es
}

function handleSSEMessage(data) {
  if (data.type === 'log' || data.type === 'info' || data.type === 'warning' || data.type === 'error') {
    logs.value.push({
      level: data.level || 'info',
      message: data.message || '',
      timestamp: data.timestamp || new Date().toISOString(),
    })
    scrollToBottom()
  } else if (data.type === 'metrics') {
    currentMetrics.value = {
      epoch: data.iteration || data.epoch || 0,
      total: data.total || config.value.max_iterations,
      map50: data.map50 || 0,
      map50_95: data.map50_95 || 0,
      loss: data.loss || data.train_loss || 0,
    }
    if (currentTask.value) {
      currentTask.value.progress = data.progress || 0
    }
  } else if (data.type === 'status') {
    if (currentTask.value) {
      currentTask.value.status = data.status
      if (data.status === 'completed' || data.status === 'failed') {
        refreshTaskInfo()
      }
    }
  } else if (data.type === 'decision_needed') {
    // Agent 需要用户决策
    agentSuggestion.value = data.llm_analysis || data.analysis || ''
    agentOptions.value = data.options || [
      { value: 'proceed', label: '⚡ 直接开始训练', desc: '使用当前数据开始训练' },
      { value: 'auto_label', label: '🤖 补充自动标注', desc: '对未标注图片做自动标注' },
      { value: 'stop', label: '⏹️ 暂停', desc: '先完善数据集' },
    ]
    selectedOption.value = ''
    scrollToBottom()
  }
}

async function confirmAgentAction() {
  if (!selectedOption.value || !currentTask.value) return
  try {
    await submitDecision(currentTask.value.task_id, selectedOption.value)
    agentSuggestion.value = ''
    agentOptions.value = []
    selectedOption.value = ''
    logs.value.push({ level: 'info', message: `✅ 用户选择: ${selectedOption.value}`, timestamp: new Date().toISOString() })
  } catch (e) {
    ElMessage.error('提交失败: ' + e.message)
  }
}

async function refreshTaskInfo() {
  if (!currentTask.value) return
  try {
    const task = await getTask(currentTask.value.task_id)
    currentTask.value = task

    // 加载迭代历史
    const iterData = await getTaskIterations(currentTask.value.task_id)
    iterations.value = iterData.iterations || []

    // 加载日志
    const logData = await getTaskLogs(currentTask.value.task_id)
    logs.value = logData.logs || []
  } catch (e) {
    console.error('refreshTaskInfo error:', e)
  }
}

async function pauseTraining() {
  if (!currentTask.value) return
  try {
    await pauseTask(currentTask.value.task_id)
    currentTask.value.status = 'paused'
    ElMessage.success('训练已暂停')
  } catch (e) {
    ElMessage.error('暂停失败: ' + e.message)
  }
}

async function resumeTraining() {
  if (!currentTask.value) return
  try {
    await resumeTask(currentTask.value.task_id)
    currentTask.value.status = 'training'
    ElMessage.success('训练已恢复')
  } catch (e) {
    ElMessage.error('恢复失败: ' + e.message)
  }
}

async function stopTraining() {
  if (!currentTask.value) return
  try {
    await stopTask(currentTask.value.task_id)
    currentTask.value.status = 'stopped'
    ElMessage.success('训练已停止')
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
  } catch (e) {
    ElMessage.error('停止失败: ' + e.message)
  }
}

function clearLogs() {
  logs.value = []
}

function scrollToBottom() {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

onMounted(() => {
  loadDatasets()
})

onUnmounted(() => {
  if (eventSource.value) {
    eventSource.value.close()
  }
})
</script>

<style scoped>
.agent-view {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.section-title {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.header-subtitle {
  color: #666;
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Layout */
.agent-layout {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 24px;
}

/* Left Panel */
.left-panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
}

.panel-section {
  margin-bottom: 24px;
}

.panel-section:last-child {
  margin-bottom: 0;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px 0;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.stat-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.stat-num {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #333;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.annotation-progress {
  margin-top: 12px;
}

/* Class Tags */
.class-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* Image Grid */
.image-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.image-item {
  aspect-ratio: 1;
  border-radius: 6px;
  overflow: hidden;
  background: #f5f7fa;
}

.image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* Right Panel */
.right-panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
}

/* Phase Indicator */
.phase-indicator {
  margin-bottom: 20px;
}

.phase-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
}

.phase-idle {
  background: #f5f7fa;
  color: #666;
}

.phase-training {
  background: #e8f4fd;
  color: #1890ff;
}

.phase-paused {
  background: #fff7e6;
  color: #faad14;
}

.phase-completed {
  background: #f6ffed;
  color: #52c41a;
}

.phase-failed {
  background: #fff1f0;
  color: #ff4d4f;
}

/* Agent Suggestion Card */
.agent-suggestion-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  padding: 20px;
  color: white;
  margin-bottom: 20px;
}

.suggestion-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.suggestion-icon {
  font-size: 20px;
}

.suggestion-title {
  font-size: 16px;
  font-weight: 600;
}

.suggestion-content {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
}

.suggestion-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
}

.action-label {
  font-size: 12px;
  opacity: 0.9;
  margin-bottom: 8px;
}

.action-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-option {
  background: rgba(255, 255, 255, 0.1);
  border: 2px solid transparent;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-option:hover {
  background: rgba(255, 255, 255, 0.2);
}

.action-option.selected {
  border-color: white;
  background: rgba(255, 255, 255, 0.25);
}

.option-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}

.option-desc {
  display: block;
  font-size: 12px;
  opacity: 0.8;
}

/* Training Metrics */
.training-metrics {
  background: #f5f7fa;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-item {
  text-align: center;
}

.metric-label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.metric-value {
  display: block;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.metric-value.metric-good {
  color: #52c41a;
}

.metric-value.metric-bad {
  color: #ff4d4f;
}

/* Iteration History */
.iteration-history {
  margin-bottom: 20px;
}

.iteration-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.iteration-item {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}

.iter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.iter-badge {
  font-weight: 600;
  font-size: 13px;
}

.iter-decision {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}

.decision-pass {
  background: #f6ffed;
  color: #52c41a;
}

.decision-fail_retry {
  background: #e6f7ff;
  color: #1890ff;
}

.decision-fail_stop {
  background: #fff1f0;
  color: #ff4d4f;
}

.iter-stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #666;
}

/* Log Panel */
.log-panel {
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}

.log-header .panel-title {
  margin: 0;
}

.log-container {
  height: 300px;
  overflow-y: auto;
  padding: 12px 16px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
}

.log-line {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid #f5f7fa;
}

.log-time {
  color: #999;
  flex-shrink: 0;
}

.log-message {
  word-break: break-all;
}

.log-info .log-message {
  color: #333;
}

.log-warning .log-message {
  color: #faad14;
}

.log-error .log-message {
  color: #ff4d4f;
}
</style>
