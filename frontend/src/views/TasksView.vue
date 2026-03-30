<template>
  <div class="tasks-view">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="section-title">训练任务</h2>
        <span class="task-count" v-if="tasks.length">{{ tasks.length }} 个任务</span>
      </div>
      <el-button type="primary" @click="showCreateDialog = true">
        + 新建任务
      </el-button>
    </div>

    <!-- Tasks Grid -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>

    <div v-else-if="tasks.length === 0">
      <EmptyState
        icon="🎯"
        title="暂无训练任务"
        description="创建一个训练任务，上传图片，Agent 将自动完成标注和训练"
      >
        <el-button type="primary" @click="showCreateDialog = true" style="margin-top: 16px">
          创建第一个任务
        </el-button>
      </EmptyState>
    </div>

    <div v-else class="tasks-grid">
      <div
        v-for="task in tasks"
        :key="task.task_id"
        class="task-card"
        @click="openDetail(task)"
      >
        <div class="task-card-header">
          <h3 class="task-name">{{ task.name }}</h3>
          <StatusBadge :status="task.status" />
        </div>

        <div class="task-meta">
          <span class="meta-item" v-if="task.yolo_model">
            {{ task.yolo_model }}
          </span>
          <span class="meta-item" v-if="task.epochs">
            {{ task.epochs }} epochs
          </span>
        </div>

        <div class="task-progress" v-if="task.status === 'training'">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: (task.progress || 0) + '%' }"></div>
          </div>
          <span class="progress-text">{{ task.progress || 0 }}%</span>
        </div>

        <div class="task-metrics" v-if="task.map50">
          <div class="metric-item">
            <span class="metric-label">mAP@50</span>
            <span class="metric-value" :class="mapClass(task.map50)">
              {{ (task.map50 * 100).toFixed(1) }}%
            </span>
          </div>
          <div class="metric-item" v-if="task.map50_95">
            <span class="metric-label">mAP</span>
            <span class="metric-value">{{ (task.map50_95 * 100).toFixed(1) }}%</span>
          </div>
        </div>

        <div class="task-actions" @click.stop>
          <el-button
            v-if="task.status === 'pending' || task.status === 'stopped'"
            type="primary"
            size="small"
            @click="startTraining(task)"
          >
            开始训练
          </el-button>
          <el-button
            v-if="task.status === 'training'"
            size="small"
            @click="pauseTask(task)"
          >
            暂停
          </el-button>
          <el-button
            v-if="task.status === 'paused'"
            type="success"
            size="small"
            @click="resumeTask(task)"
          >
            恢复
          </el-button>
          <el-button
            v-if="task.status === 'training' || task.status === 'paused'"
            type="danger"
            size="small"
            @click="stopTraining(task)"
          >
            停止
          </el-button>
          <el-button
            v-if="task.status === 'completed'"
            type="success"
            size="small"
            @click="$router.push('/models')"
          >
            查看模型
          </el-button>
          <el-button
            v-if="task.status !== 'training' && task.status !== 'paused'"
            type="danger"
            text
            size="small"
            @click="deleteTask(task)"
          >
            删除
          </el-button>
        </div>
      </div>
    </div>

    <!-- Create Task Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建训练任务"
      width="480px"
      destroy-on-close
    >
      <el-form label-position="top" :model="createForm">
        <el-form-item label="任务名称">
          <el-input
            v-model="createForm.name"
            placeholder="例如：安全帽检测"
          />
        </el-form-item>
        <el-form-item label="数据集">
          <el-select v-model="createForm.datasetId" style="width: 100%">
            <el-option
              v-for="ds in datasets"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="3"
            placeholder="描述要检测的目标，例如：检测照片中的人物是否佩戴安全帽"
          />
        </el-form-item>
        <el-form-item label="检测类别（逗号分隔）">
          <el-input
            v-model="createForm.classes"
            placeholder="未戴安全帽, 未戴手套, 火灾"
          />
        </el-form-item>
        <el-form-item label="模型大小">
          <el-select v-model="createForm.yolo_model" style="width: 100%">
            <el-option label="YOLOv8n (最小)" value="yolov8n" />
            <el-option label="YOLOv8s (小)" value="yolov8s" />
            <el-option label="YOLOv8m (中)" value="yolov8m" />
            <el-option label="YOLOv8l (大)" value="yolov8l" />
            <el-option label="YOLOv8x (最大)" value="yolov8x" />
          </el-select>
        </el-form-item>
        <el-form-item label="训练轮数">
          <el-input-number
            v-model="createForm.epochs"
            :min="10"
            :max="1000"
            :step="10"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="训练模式">
          <el-radio-group v-model="createForm.trainingType">
            <el-radio label="agent">🤖 Agent 智能训练（自动调参迭代）</el-radio>
            <el-radio label="regular">⚡ 常规训练（固定参数，单次）</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createTask">
          创建任务
        </el-button>
      </template>
    </el-dialog>

    <!-- Task Detail Dialog -->
    <el-dialog
      v-model="showDetailDialog"
      :title="selectedTask?.name"
      width="800px"
      destroy-on-close
    >
      <div class="detail-content" v-if="selectedTask">
        <!-- Status -->
        <div class="detail-section">
          <div class="detail-row">
            <span class="detail-label">状态</span>
            <StatusBadge :status="selectedTask.status" />
          </div>
          <div class="detail-row" v-if="selectedTask.progress">
            <span class="detail-label">进度</span>
            <div class="progress-inline">
              <el-progress
                :percentage="selectedTask.progress"
                :stroke-width="8"
                style="width: 200px"
              />
            </div>
          </div>
          <div class="detail-row" v-if="selectedTask.error_message">
            <span class="detail-label">失败原因</span>
            <span class="error-message">{{ selectedTask.error_message }}</span>
          </div>
        </div>

        <!-- Metrics -->
        <div class="detail-section" v-if="metrics.length">
          <h4 class="section-subtitle">训练指标</h4>
          <div class="metrics-grid">
            <div class="metric-card" v-for="m in metrics" :key="m.epoch">
              <div class="mc-epoch">Epoch {{ m.epoch }}</div>
              <div class="mc-val">
                <span class="mc-label">mAP@50</span>
                <span class="mc-value" :class="mapClass(m.map50)">
                  {{ m.map50 ? (m.map50 * 100).toFixed(1) + '%' : '-' }}
                </span>
              </div>
              <div class="mc-val">
                <span class="mc-label">Loss</span>
                <span class="mc-value">{{ m.train_loss ? m.train_loss.toFixed(3) : '-' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Iterations -->
        <div class="detail-section" v-if="iterations.length">
          <h4 class="section-subtitle">迭代历史</h4>
          <el-table :data="iterations" size="small">
            <el-table-column prop="iteration" label="迭代" width="70" />
            <el-table-column prop="yolo_model" label="模型" />
            <el-table-column prop="epochs" label="Epochs" />
            <el-table-column label="mAP@50" width="90">
              <template #default="{ row }">
                <span :class="mapClass(row.map50)">
                  {{ row.map50 ? (row.map50 * 100).toFixed(1) + '%' : '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="decision" label="决策" />
          </el-table>
        </div>

        <!-- Logs -->
        <div class="detail-section" v-if="logs.length">
          <h4 class="section-subtitle">训练日志</h4>
          <div class="log-container">
            <div
              v-for="(log, i) in logs.slice(-50)"
              :key="i"
              class="log-line"
              :class="`log-${log.level}`"
            >
              <span class="log-time">{{ formatTime(log.timestamp) }}</span>
              {{ log.message }}
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="detail-footer">
          <div class="footer-left">
            <el-tag v-if="selectedTask?.training_type === 'agent'" type="primary">🤖 Agent</el-tag>
            <el-tag v-else type="warning">⚡ 常规</el-tag>
          </div>
          <el-button
            v-if="selectedTask?.status !== 'training' && selectedTask?.status !== 'paused'"
            type="danger"
            text
            size="small"
            @click="deleteTask(selectedTask); showDetailDialog = false"
          >
            删除任务
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StatusBadge from '../components/common/StatusBadge.vue'
import EmptyState from '../components/common/EmptyState.vue'
import { getTasks, createTask as apiCreateTask, startTask, stopTask, deleteTask as apiDeleteTask, pauseTask as apiPauseTask, resumeTask as apiResumeTask, getTaskLogs, getTaskMetrics, getTaskIterations, createTaskStream } from '../api/tasks'
import { getDatasets } from '../api/datasets'

const tasks = ref([])
const datasets = ref([])
const loading = ref(true)
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const selectedTask = ref(null)
const creating = ref(false)
const metrics = ref([])
const iterations = ref([])
const logs = ref([])
let stream = null

const createForm = ref({
  name: '',
  description: '',
  classes: '',
  datasetId: 'demo',
  yolo_model: 'yolov8n',
  epochs: 100,
  trainingType: 'agent',
})

async function loadDatasets() {
  try {
    const data = await getDatasets()
    datasets.value = data.datasets || []
    if (datasets.value.length && !createForm.value.datasetId) {
      createForm.value.datasetId = datasets.value[0].id
    }
  } catch (e) {
    datasets.value = [{ id: 'demo', name: '演示数据集' }]
  }
}

async function loadTasks() {
  try {
    const data = await getTasks()
    tasks.value = data.tasks || []
  } catch (e) {
    ElMessage.error('加载任务失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function createTask() {
  if (!createForm.value.name) {
    ElMessage.warning('请输入任务名称')
    return
  }
  if (!createForm.value.classes) {
    ElMessage.warning('请输入检测类别')
    return
  }
  creating.value = true
  try {
    const classList = createForm.value.classes.split(',').map(s => s.trim()).filter(Boolean)
    await apiCreateTask({
      name: createForm.value.name,
      description: createForm.value.description,
      class_names: classList,
      dataset_id: createForm.value.datasetId,
      yolo_model: createForm.value.yolo_model,
      epochs: createForm.value.epochs,
      training_type: createForm.value.trainingType,
    })
    ElMessage.success('任务创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '', description: '', classes: '', datasetId: createForm.value.datasetId || 'demo', yolo_model: 'yolov8n', epochs: 100, trainingType: 'agent' }
    await loadTasks()
  } catch (e) {
    ElMessage.error('创建失败: ' + e.message)
  } finally {
    creating.value = false
  }
}

async function startTraining(task) {
  try {
    await startTask(task.task_id)
    ElMessage.success('训练已启动')
    await loadTasks()
    // Auto open detail to see streaming
    openDetail(task)
  } catch (e) {
    ElMessage.error('启动失败: ' + e.message)
  }
}

async function stopTraining(task) {
  try {
    await stopTask(task.task_id)
    ElMessage.success('训练已停止')
    await loadTasks()
  } catch (e) {
    ElMessage.error('停止失败: ' + e.message)
  }
}

async function pauseTask(task) {
  try {
    await apiPauseTask(task.task_id)
    ElMessage.success('训练已暂停')
    await loadTasks()
  } catch (e) {
    ElMessage.error('暂停失败: ' + e.message)
  }
}

async function resumeTask(task) {
  try {
    await apiResumeTask(task.task_id)
    ElMessage.success('训练已恢复')
    await loadTasks()
  } catch (e) {
    ElMessage.error('恢复失败: ' + e.message)
  }
}

async function deleteTask(task) {
  try {
    await ElMessageBox.confirm(`确定要删除任务"${task.name}"吗？`, '删除确认', { type: 'warning' })
    await apiDeleteTask(task.task_id)
    ElMessage.success('删除成功')
    await loadTasks()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + e.message)
    }
  }
}

async function openDetail(task) {
  selectedTask.value = task
  showDetailDialog.value = true
  metrics.value = []
  iterations.value = []
  logs.value = []

  // Load data
  try {
    const [mData, iData, lData] = await Promise.all([
      getTaskMetrics(task.task_id).catch(() => ({ metrics: [] })),
      getTaskIterations(task.task_id).catch(() => ({ iterations: [] })),
      getTaskLogs(task.task_id, 50).catch(() => ({ logs: [] })),
    ])
    metrics.value = mData.metrics || []
    iterations.value = iData.iterations || []
    logs.value = lData.logs || []
  } catch {}

  // Start SSE stream
  if (stream) stream.close()
  stream = createTaskStream(task.task_id, {
    onMessage(data) {
      if (data.type === 'status' || data.type === 'log' || data.type === 'metric') {
        if (selectedTask.value?.task_id === task.task_id) {
          selectedTask.value = { ...selectedTask.value, ...data }
          if (data.progress !== undefined) {
            selectedTask.value.progress = data.progress
          }
          if (data.logs) logs.value = data.logs.slice(-50)
          if (data.metrics) metrics.value = data.metrics
        }
        // Update task in list
        const idx = tasks.value.findIndex(t => t.task_id === task.task_id)
        if (idx >= 0) {
          tasks.value[idx] = { ...tasks.value[idx], ...data }
        }
      }
    },
    onError() {
      stream = null
    },
  })
}

function mapClass(val) {
  if (!val) return ''
  return val >= 0.82 ? 'metric-good' : 'metric-bad'
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString()
}

onMounted(async () => {
  await Promise.all([loadTasks(), loadDatasets()])
})
onUnmounted(() => { if (stream) stream.close() })
</script>

<style scoped>
.tasks-view {
  max-width: 1200px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-6);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.section-title {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}

.task-count {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  background: var(--color-surface-2);
  padding: 2px 10px;
  border-radius: var(--radius-full);
}

/* Loading */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-12);
  gap: var(--space-3);
  color: var(--color-text-muted);
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Tasks Grid */
.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-4);
}

.task-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.task-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-primary-light);
}

.task-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.task-name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--color-text);
  line-height: 1.3;
}

.task-meta {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.meta-item {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  background: var(--color-surface-2);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.task-progress {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: var(--color-surface-2);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: var(--radius-full);
  transition: width 0.5s ease;
}

.progress-text {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  min-width: 36px;
}

.task-metrics {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-3);
  padding: var(--space-3);
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.metric-value {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
}

.metric-good { color: var(--color-secondary); }
.metric-bad { color: var(--color-danger); }

.task-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border-light);
}

/* Dialog detail */
.detail-section {
  margin-bottom: var(--space-5);
}

.section-subtitle {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-3);
}

.detail-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}

.detail-label {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  min-width: 60px;
}

.progress-inline {
  flex: 1;
}

.error-message {
  font-size: var(--text-sm);
  color: var(--color-danger);
  word-break: break-all;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--space-3);
}

.metric-card {
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
}

.mc-epoch {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  margin-bottom: var(--space-2);
}

.mc-val {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.mc-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.mc-value {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
}

.log-container {
  background: #1e1e1e;
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  max-height: 200px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.log-line {
  color: #d4d4d4;
  padding: 2px 0;
}

.log-time {
  color: #6a9955;
  margin-right: var(--space-2);
}

.log-error { color: #f48771; }
.log-warning { color: #dcdcaa; }

.detail-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.footer-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
