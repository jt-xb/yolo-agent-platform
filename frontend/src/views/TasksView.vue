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

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>

    <!-- Empty -->
    <div v-else-if="tasks.length === 0">
      <EmptyState icon="🎯" title="暂无训练任务" description="创建一个训练任务，使用数据集训练 YOLO 模型">
        <el-button type="primary" @click="showCreateDialog = true" style="margin-top: 16px">
          创建第一个任务
        </el-button>
      </EmptyState>
    </div>

    <!-- Tasks Grid -->
    <div v-else class="tasks-grid">
      <div
        v-for="task in tasks"
        :key="task.task_id"
        class="task-card"
        :class="{ 'card-active': detailTaskId === task.task_id && showDetailDialog }"
        @click="openDetail(task)"
      >
        <div class="task-card-header">
          <h3 class="task-name">{{ task.name }}</h3>
          <StatusBadge :status="task.status" />
        </div>

        <div class="task-meta">
          <span class="meta-item" v-if="task.yolo_model">{{ task.yolo_model }}</span>
          <span class="meta-item" v-if="task.epochs">{{ task.epochs }} epochs</span>
          <span class="meta-item">⚡ 常规</span>
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
            @click="$router.push({ path: '/models', query: { task_id: task.task_id } })"
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
    <el-dialog v-model="showCreateDialog" title="新建训练任务" width="520px" destroy-on-close>
      <el-form label-position="top" :model="createForm">
        <el-form-item label="任务名称">
          <el-input v-model="createForm.name" placeholder="例如：安全帽检测" />
        </el-form-item>
        <el-form-item label="数据集">
          <el-select v-model="createForm.datasetId" style="width: 100%">
            <el-option v-for="ds in datasets" :key="ds.id" :label="ds.name" :value="ds.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="YOLO 模型">
          <el-select v-model="createForm.yoloModel" style="width: 100%">
            <el-option label="YOLOv8n (最小，最快)" value="yolov8n" />
            <el-option label="YOLOv8s (小)" value="yolov8s" />
            <el-option label="YOLOv8m (中)" value="yolov8m" />
            <el-option label="YOLOv8l (大)" value="yolov8l" />
            <el-option label="YOLOv8x (最大，最准)" value="yolov8x" />
          </el-select>
        </el-form-item>
        <el-form-item label="训练轮数">
          <el-input-number v-model="createForm.epochs" :min="10" :max="1000" :step="10" style="width: 100%" />
        </el-form-item>
        <el-form-item label="检测类别（逗号分隔）">
          <el-input v-model="createForm.classes" placeholder="person, helmet, no_helmet" />
        </el-form-item>
        <el-form-item label="任务描述（可选）">
          <el-input v-model="createForm.description" type="textarea" :rows="2" placeholder="描述要检测的目标" />
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
      :title="selectedTask?.name || '任务详情'"
      width="860px"
      @closed="onDetailClosed"
    >
      <div class="detail-content" v-if="selectedTask">
        <!-- 状态区 -->
        <div class="detail-section">
          <div class="detail-row">
            <span class="detail-label">状态</span>
            <StatusBadge :status="selectedTask.status" />
            <span class="meta-item" style="margin-left:8px">⚡ 常规训练</span>
          </div>
          <div class="detail-row" v-if="selectedTask.progress > 0">
            <span class="detail-label">进度</span>
            <div class="progress-inline">
              <el-progress :percentage="Math.round(selectedTask.progress)" :stroke-width="8" style="width:220px" />
            </div>
          </div>
          <div class="detail-row" v-if="selectedTask.error_message">
            <span class="detail-label">失败原因</span>
            <span class="error-message">{{ selectedTask.error_message }}</span>
          </div>
        </div>

        <!-- 实时指标卡（流式） -->
        <div class="detail-section" v-if="liveMetrics.length">
          <h4 class="section-subtitle">
            📊 实时指标
            <span class="log-count" v-if="liveMetrics.length > 20">(显示最后20轮)</span>
          </h4>
          <div class="metrics-grid">
            <div class="metric-card" v-for="m in liveMetrics.slice(-20)" :key="m.epoch">
              <div class="mc-epoch">Epoch {{ m.epoch }}/{{ m.total || selectedTask.epochs }}</div>
              <div class="mc-val">
                <span class="mc-label">mAP50</span>
                <span class="mc-value" :class="mapClass(m.map50)">
                  {{ m.map50 != null ? (m.map50 * 100).toFixed(1) + '%' : '-' }}
                </span>
              </div>
              <div class="mc-val">
                <span class="mc-label">Loss</span>
                <span class="mc-value">{{ (m.loss ?? m.train_loss) != null ? (m.loss ?? m.train_loss).toFixed(3) : '-' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 迭代历史 -->
        <div class="detail-section" v-if="iterations.length">
          <h4 class="section-subtitle">训练历史</h4>
          <el-table :data="iterations" size="small" max-height="200">
            <el-table-column prop="epoch" label="Epoch" width="70" />
            <el-table-column prop="yolo_model" label="模型" />
            <el-table-column label="mAP@50" width="90">
              <template #default="{ row }">
                <span :class="mapClass(row.metrics?.map50)">
                  {{ row.metrics?.map50 != null ? (row.metrics.map50 * 100).toFixed(1) + '%' : '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="Loss" width="80">
              <template #default="{ row }">
                {{ row.metrics?.loss != null ? row.metrics.loss.toFixed(3) : '-' }}
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 训练日志（流式） -->
        <div class="detail-section">
          <h4 class="section-subtitle">
            📋 训练日志
            <span class="log-count" v-if="logs.length">({{ logs.length }} 条)</span>
          </h4>
          <div class="log-container" ref="logContainerRef">
            <div
              v-for="(log, i) in logs.slice(-80)"
              :key="i"
              class="log-line"
              :class="`log-${log.level || 'info'}`"
            >
              <span class="log-time">{{ formatTime(log.timestamp) }}</span>
              {{ log.message }}
            </div>
            <div v-if="!logs.length" class="log-empty">暂无日志，开始训练后将实时显示...</div>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="detail-footer" v-if="selectedTask">
          <div class="footer-left">
            <el-tag type="info" v-if="selectedTask.yolo_model">{{ selectedTask.yolo_model }}</el-tag>
            <el-tag type="info" v-if="selectedTask.epochs">{{ selectedTask.epochs }} epochs</el-tag>
          </div>
          <el-button
            v-if="selectedTask.status !== 'training' && selectedTask.status !== 'paused'"
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
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StatusBadge from '../components/common/StatusBadge.vue'
import EmptyState from '../components/common/EmptyState.vue'
import {
  getTasks, createTask as apiCreateTask, startTask, stopTask,
  deleteTask as apiDeleteTask, pauseTask as apiPauseTask, resumeTask as apiResumeTask,
  getTaskLogs, getTaskMetrics, getTaskIterations, createTaskStream
} from '../api/tasks'
import { getDatasets } from '../api/datasets'

const tasks = ref([])
const datasets = ref([])
const loading = ref(true)
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const selectedTask = ref(null)
const detailTaskId = ref(null)
const creating = ref(false)
const liveMetrics = ref([])
const iterations = ref([])
const logs = ref([])
const logContainerRef = ref(null)

// SSE stream 实例（每次打开独立，关闭时清理）
let currentStream = null
let logPollingTimer = null

const createForm = ref({
  name: '',
  description: '',
  classes: '',
  datasetId: 'demo',
  yoloModel: 'yolov8n',
  epochs: 100,
})

// ============================================
async function loadDatasets() {
  try {
    const data = await getDatasets()
    datasets.value = data.datasets || []
    if (datasets.value.length && !createForm.value.datasetId) {
      createForm.value.datasetId = datasets.value[0].id
    }
  } catch {
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
      yolo_model: createForm.value.yoloModel,
      epochs: createForm.value.epochs,
    })
    ElMessage.success('任务创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '', description: '', classes: '', datasetId: createForm.value.datasetId || 'demo', yoloModel: 'yolov8n', epochs: 100 }
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
    if (detailTaskId.value === task.task_id) {
      closeDetail()
    }
    await loadTasks()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败: ' + e.message)
  }
}

// ============================================
// 详情页：SSE 流式日志 + 轮询补全
// ============================================

function closeDetail() {
  // 清理 SSE
  if (currentStream) {
    currentStream.close()
    currentStream = null
  }
  // 清理轮询
  if (logPollingTimer) {
    clearInterval(logPollingTimer)
    logPollingTimer = null
  }
  // 如果 dialog 正在显示中（被 openDetail 重新打开了），不清理状态
  if (showDetailDialog.value) {
    return
  }
  showDetailDialog.value = false
  selectedTask.value = null
  detailTaskId.value = null
  liveMetrics.value = []
  iterations.value = []
  logs.value = []
}

function onDetailClosed() {
  closeDetail()
}

async function openDetail(task) {
  // 关闭旧的
  closeDetail()

  // 重置状态
  selectedTask.value = task
  detailTaskId.value = task.task_id
  liveMetrics.value = []
  iterations.value = []
  logs.value = []
  showDetailDialog.value = true

  // 加载历史数据（从 DB）
  try {
    console.log('[DEBUG] openDetail called, task_id:', task.task_id)
    const [mData, iData, lData] = await Promise.all([
      getTaskMetrics(task.task_id).catch(() => ({ metrics: [] })),
      getTaskIterations(task.task_id).catch(() => ({ iterations: [] })),
      getTaskLogs(task.task_id, 100).catch(() => {
        console.log('[DEBUG] getTaskLogs failed')
        return { logs: [] }
      }),
    ])
    console.log('[DEBUG] getTaskLogs response:', lData, 'logs length:', lData?.logs?.length, 'task_id:', task.task_id)
    liveMetrics.value = mData.metrics || []
    iterations.value = iData.iterations || []
    logs.value = lData.logs || []
    console.log('[DEBUG] logs.value after assignment:', logs.value.length, 'showDetailDialog:', showDetailDialog.value)
    scrollLogToBottom()
  } catch (e) {
    console.error('[DEBUG] Error loading history:', e)
  }

  // 启动 SSE 流（实时接收新数据）
  startSSEStream(task.task_id)

  // 每 3 秒轮询补全（防止 SSE 漏消息）
  logPollingTimer = setInterval(async () => {
    if (!showDetailDialog.value) return
    try {
      const lData = await getTaskLogs(task.task_id, 50).catch(() => ({ logs: [] }))
      if (lData.logs && lData.logs.length > logs.value.length) {
        logs.value = lData.logs.slice(-100)
        scrollLogToBottom()
      }
      const mData = await getTaskMetrics(task.task_id).catch(() => ({ metrics: [] }))
      if (mData.metrics && mData.metrics.length > liveMetrics.value.length) {
        liveMetrics.value = mData.metrics
      }
    } catch {}
  }, 3000)
}

function startSSEStream(taskId) {
  if (currentStream) {
    currentStream.close()
    currentStream = null
  }

  currentStream = createTaskStream(taskId, {
    onMessage(data) {
      if (!selectedTask.value || selectedTask.value.task_id !== taskId) return

      if (data.type === 'log' || data.type === 'log') {
        logs.value.push(data)
        if (logs.value.length > 200) logs.value = logs.value.slice(-100)
        nextTick(scrollLogToBottom)
      }

      if (data.type === 'metrics') {
        // 合并到 liveMetrics（去重）
        const existIdx = liveMetrics.value.findIndex(m => m.epoch === data.epoch)
        if (existIdx >= 0) {
          liveMetrics.value[existIdx] = data
        } else {
          liveMetrics.value.push(data)
        }
      }

      if (data.type === 'status') {
        // 更新任务状态和进度
        selectedTask.value = { ...selectedTask.value, status: data.status, progress: data.progress }
        // 同步到 tasks 列表
        const idx = tasks.value.findIndex(t => t.task_id === taskId)
        if (idx >= 0) {
          tasks.value[idx] = { ...tasks.value[idx], status: data.status, progress: data.progress, map50: data.map50 || tasks.value[idx].map50 }
        }
        // 训练结束，清理轮询
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
          if (logPollingTimer) {
            clearInterval(logPollingTimer)
            logPollingTimer = null
          }
        }
      }
    },
    onError() {
      // SSE 断开，轮询会补偿
      if (currentStream) {
        currentStream.close()
        currentStream = null
      }
    },
  })
}

function scrollLogToBottom() {
  nextTick(() => {
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    }
  })
}

function mapClass(val) {
  if (!val) return ''
  return val >= 0.82 ? 'metric-good' : 'metric-bad'
}

function formatTime(ts) {
  if (!ts) return ''
  if (typeof ts === 'string' && ts.length >= 8) {
    const match = ts.match(/T(\d{2}:\d{2}:\d{2})/) || ts.match(/^(\d{2}:\d{2}:\d{2})/)
    if (match) return match[1]
  }
  try { return new Date(ts).toLocaleTimeString() } catch { return '' }
}

onMounted(async () => {
  await Promise.all([loadTasks(), loadDatasets()])
})

onUnmounted(() => {
  closeDetail()
})
</script>

<style scoped>
.tasks-view { max-width: 1200px; }

.page-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: var(--space-6);
}
.header-left { display: flex; align-items: center; gap: var(--space-3); }
.section-title { font-size: var(--text-xl); font-weight: var(--font-semibold); color: var(--color-text); }
.task-count {
  font-size: var(--text-sm); color: var(--color-text-muted);
  background: var(--color-surface-2); padding: 2px 10px; border-radius: var(--radius-full);
}

/* Loading */
.loading-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: var(--space-12); gap: var(--space-3); color: var(--color-text-muted);
}
.spinner {
  width: 32px; height: 32px; border: 3px solid var(--color-border);
  border-top-color: var(--color-primary); border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Tasks Grid */
.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-4);
}
.task-card {
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: var(--radius-md); padding: var(--space-4);
  cursor: pointer; transition: all var(--transition-fast);
}
.task-card:hover { box-shadow: var(--shadow-md); border-color: var(--color-primary-light); }
.task-card.card-active { border-color: var(--color-primary); background: color-mix(in srgb, var(--color-primary) 5%, var(--color-surface)); }
.task-card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); }
.task-name { font-size: var(--text-md); font-weight: var(--font-semibold); line-height: 1.3; }
.task-meta { display: flex; gap: var(--space-2); flex-wrap: wrap; margin-bottom: var(--space-3); }
.meta-item {
  font-size: var(--text-xs); color: var(--color-text-muted);
  background: var(--color-surface-2); padding: 2px 8px; border-radius: var(--radius-sm);
}
.task-progress { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
.progress-bar { flex: 1; height: 6px; background: var(--color-surface-2); border-radius: var(--radius-full); overflow: hidden; }
.progress-fill { height: 100%; background: var(--color-primary); border-radius: var(--radius-full); transition: width 0.5s; }
.progress-text { font-size: var(--text-xs); color: var(--color-text-muted); min-width: 36px; }
.task-metrics {
  display: flex; gap: var(--space-4); margin-bottom: var(--space-3);
  padding: var(--space-3); background: var(--color-surface-2); border-radius: var(--radius-sm);
}
.metric-item { display: flex; flex-direction: column; gap: 2px; }
.metric-label { font-size: var(--text-xs); color: var(--color-text-muted); }
.metric-value { font-size: var(--text-sm); font-weight: var(--font-semibold); }
.metric-good { color: var(--color-secondary); }
.metric-bad { color: var(--color-danger); }
.task-actions {
  display: flex; gap: var(--space-2); padding-top: var(--space-3);
  border-top: 1px solid var(--color-border-light); flex-wrap: wrap;
}

/* Create dialog */
.form-tip { font-size: var(--text-xs); color: var(--color-text-muted); margin-top: 6px; }

/* Detail dialog */
.detail-section { margin-bottom: var(--space-5); }
.section-subtitle {
  font-size: var(--text-sm); font-weight: var(--font-semibold);
  color: var(--color-text-secondary); margin-bottom: var(--space-3);
  display: flex; align-items: center; gap: var(--space-2);
}
.log-count { font-weight: normal; color: var(--color-text-muted); }
.detail-row { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) 0; }
.detail-label { font-size: var(--text-sm); color: var(--color-text-muted); min-width: 60px; }
.progress-inline { flex: 1; }
.error-message { font-size: var(--text-sm); color: var(--color-danger); word-break: break-all; }

/* Metrics grid */
.metrics-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: var(--space-3);
}
.metric-card { background: var(--color-surface-2); border-radius: var(--radius-sm); padding: var(--space-3); }
.mc-epoch { font-size: var(--text-xs); color: var(--color-text-muted); margin-bottom: var(--space-2); }
.mc-val { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.mc-label { font-size: var(--text-xs); color: var(--color-text-muted); }
.mc-value { font-size: var(--text-sm); font-weight: var(--font-semibold); }

/* Log container */
.log-container {
  background: #1e1e1e; border-radius: var(--radius-sm); padding: var(--space-3);
  max-height: 240px; overflow-y: auto; font-family: var(--font-mono);
  font-size: var(--text-xs); display: flex; flex-direction: column; gap: 1px;
}
.log-line { color: #d4d4d4; padding: 1px 0; white-space: pre-wrap; word-break: break-all; }
.log-time { color: #6a9955; margin-right: var(--space-2); flex-shrink: 0; }
.log-error { color: #f48771; }
.log-warning { color: #dcdcaa; }
.log-empty { color: #666; text-align: center; padding: var(--space-4); }

/* Footer */
.detail-footer { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.footer-left { display: flex; align-items: center; gap: var(--space-2); }
</style>
