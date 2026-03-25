<template>
  <div class="tasks-view">
    <!-- 页面标题区 -->
    <div class="page-header">
      <div class="page-title-area">
        <h2>🎯 训练任务管理</h2>
        <p class="page-subtitle">创建训练任务后，Agent 将自动分析效果并迭代优化，全程无需人工干预</p>
      </div>
      <el-button type="primary" size="large" @click="showCreateDialog = true" class="create-btn">
        <span class="btn-icon">+</span> 新建训练任务
      </el-button>
    </div>

    <!-- 训练流程示意图（当有训练中任务时显示） -->
    <div class="training-flow-diagram" v-if="trainingTasks.length > 0">
      <div class="flow-step" v-for="(step, i) in trainingFlowSteps" :key="i" :class="{ active: step.active, completed: step.completed }">
        <div class="flow-icon">{{ step.icon }}</div>
        <div class="flow-label">{{ step.label }}</div>
        <div class="flow-arrow" v-if="i < trainingFlowSteps.length - 1">→</div>
      </div>
    </div>

    <!-- 任务列表 -->
    <el-table :data="tasks" stripe style="width: 100%; margin-top: 16px;" v-loading="loading" @row-click="handleRowClick">
      <el-table-column prop="task_id" label="任务ID" width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <code class="task-id">{{ row.task_id.slice(0, 16) }}...</code>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="任务名称" min-width="140">
        <template #default="{ row }">
          <div class="task-name-cell">
            <span class="task-name">{{ row.name || '未命名任务' }}</span>
            <el-tag v-if="row.status === 'training'" size="small" type="primary" class="agent-tag">
              🤖 Agent 训练中
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="130">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)" :class="'status-tag-' + row.status">
            <span v-if="row.status === 'training'" class="pulse-dot"></span>
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="progress" label="训练进度" width="160">
        <template #default="{ row }">
          <div class="progress-cell">
            <el-progress :percentage="row.progress || 0" :status="getProgressStatus(row.status)" :stroke-width="8" />
            <span class="progress-text">{{ row.progress || 0 }}%</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="mAP@50" width="100">
        <template #default="{ row }">
          <span v-if="row.map50" class="metric-value" :class="getMetricClass(row.map50, 0.85)">
            {{ (row.map50 * 100).toFixed(1) }}%
          </span>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="迭代次数" width="100">
        <template #default="{ row }">
          <span v-if="row.iterations">{{ row.iterations }}次</span>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="yolo_model" label="模型" width="100">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.yolo_model || 'yolov8' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click.stop="viewDetail(row)">详情</el-button>
          <el-button
            v-if="row.status === 'pending' || row.status === 'stopped'"
            size="small"
            type="success"
            @click.stop="startTask(row)"
          >▶ 启动</el-button>
          <el-button
            v-if="row.status === 'training'"
            size="small"
            type="danger"
            @click.stop="stopTask(row)"
          >■ 停止</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建任务对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建训练任务" width="600px">
      <el-form :model="newTask" label-width="100px">
        <el-form-item label="任务名称">
          <el-input v-model="newTask.name" placeholder="如：安全帽检测" />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input
            v-model="newTask.description"
            type="textarea"
            :rows="3"
            placeholder="用自然语言描述任务，如：检测图片中未佩戴安全帽的人员"
          />
        </el-form-item>
        <el-form-item label="检测类别">
          <el-select
            v-model="newTask.class_names"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入类别后回车添加"
            style="width: 100%"
          >
            <el-option
              v-for="cls in newTask.class_names"
              :key="cls"
              :label="cls"
              :value="cls"
            />
          </el-select>
          <div class="form-tip">例如：person, helmet, no_helmet</div>
        </el-form-item>
        <el-form-item label="数据路径">
          <el-input v-model="newTask.data_path" placeholder="/data/my_dataset（可选）" />
        </el-form-item>
        <el-form-item label="训练轮数">
          <el-input-number v-model="newTask.epochs" :min="10" :max="1000" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- 任务详情对话框 - Agent 核心展示区 -->
    <el-dialog
      v-model="showDetailDialog"
      :title="'🤖 Agent 训练详情 - ' + (selectedTask?.name || '')"
      width="1100px"
      :close-on-click-modal="false"
      class="agent-detail-dialog"
    >
      <div v-if="selectedTask" class="detail-content">
        <!-- 顶部状态概览 -->
        <div class="detail-header">
          <div class="detail-status-card">
            <div class="status-badge" :class="'status-' + selectedTask.status">
              <span v-if="selectedTask.status === 'training'" class="pulse-ring"></span>
              {{ getStatusText(selectedTask.status) }}
            </div>
            <div class="task-meta">
              <span class="meta-item">
                <span class="meta-icon">📊</span>
                迭代 {{ currentIteration }} / {{ maxIterations }}
              </span>
              <span class="meta-item" v-if="selectedTask.yolo_model">
                <span class="meta-icon">🤖</span>
                {{ selectedTask.yolo_model }}
              </span>
              <span class="meta-item">
                <span class="meta-icon">⏱️</span>
                {{ formatDuration(selectedTask.started_at) }}
              </span>
            </div>
          </div>

          <!-- Agent 当前行为指示器 -->
          <div class="agent-indicator" v-if="selectedTask.status === 'training'">
            <div class="agent-thinking">
              <span class="thinking-icon">🤖</span>
              <div class="thinking-text">
                <span class="thinking-label">Agent 正在分析</span>
                <span class="thinking-action">{{ agentCurrentAction }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 指标仪表板 -->
        <div class="metrics-dashboard">
          <div class="metric-gauge">
            <div class="gauge-header">
              <span class="gauge-title">mAP@50</span>
              <span class="gauge-target">目标: 85%</span>
            </div>
            <div class="gauge-bar">
              <div class="gauge-fill" :style="{ width: (selectedTask.map50 || 0) * 100 + '%' }"></div>
              <div class="gauge-marker" style="left: 85%"></div>
            </div>
            <div class="gauge-value" :class="getMetricClass(selectedTask.map50, 0.85)">
              {{ selectedTask.map50 ? (selectedTask.map50 * 100).toFixed(1) + '%' : '-' }}
            </div>
          </div>

          <div class="metric-gauge">
            <div class="gauge-header">
              <span class="gauge-title">mAP@50-95</span>
              <span class="gauge-target">目标: 65%</span>
            </div>
            <div class="gauge-bar">
              <div class="gauge-fill map95" :style="{ width: (selectedTask.map50_95 || 0) * 100 + '%' }"></div>
              <div class="gauge-marker" style="left: 65%"></div>
            </div>
            <div class="gauge-value" :class="getMetricClass(selectedTask.map50_95, 0.65)">
              {{ selectedTask.map50_95 ? (selectedTask.map50_95 * 100).toFixed(1) + '%' : '-' }}
            </div>
          </div>

          <div class="metric-gauge">
            <div class="gauge-header">
              <span class="gauge-title">Precision</span>
              <span class="gauge-target">目标: 80%</span>
            </div>
            <div class="gauge-bar">
              <div class="gauge-fill precision" :style="{ width: (selectedTask.precision || 0) * 100 + '%' }"></div>
              <div class="gauge-marker" style="left: 80%"></div>
            </div>
            <div class="gauge-value" :class="getMetricClass(selectedTask.precision, 0.80)">
              {{ selectedTask.precision ? (selectedTask.precision * 100).toFixed(1) + '%' : '-' }}
            </div>
          </div>

          <div class="metric-gauge">
            <div class="gauge-header">
              <span class="gauge-title">Recall</span>
              <span class="gauge-target">目标: 75%</span>
            </div>
            <div class="gauge-bar">
              <div class="gauge-fill recall" :style="{ width: (selectedTask.recall || 0) * 100 + '%' }"></div>
              <div class="gauge-marker" style="left: 75%"></div>
            </div>
            <div class="gauge-value" :class="getMetricClass(selectedTask.recall, 0.75)">
              {{ selectedTask.recall ? (selectedTask.recall * 100).toFixed(1) + '%' : '-' }}
            </div>
          </div>
        </div>

        <!-- Agent 决策流程时间线 -->
        <div class="agent-timeline" v-if="iterations.length > 0">
          <h3 class="section-title">
            <span class="section-icon">🔄</span>
            Agent 迭代决策流程
          </h3>
          <div class="timeline">
            <div
              v-for="(iter, i) in iterations"
              :key="i"
              class="timeline-item"
              :class="{ current: i === iterations.length - 1 && selectedTask.status === 'training', completed: iter.decision === 'pass' }"
            >
              <div class="timeline-marker">
                <span v-if="iter.decision === 'pass'" class="marker-icon">✅</span>
                <span v-else-if="iter.decision === 'fail_retry'" class="marker-icon">🔧</span>
                <span v-else class="marker-number">{{ i + 1 }}</span>
              </div>
              <div class="timeline-content">
                <div class="timeline-header">
                  <span class="iteration-label">第 {{ i + 1 }} 次迭代</span>
                  <el-tag size="small" :type="iter.decision === 'pass' ? 'success' : 'primary'" class="decision-tag">
                    {{ getDecisionText(iter.decision) }}
                  </el-tag>
                </div>
                <div class="timeline-metrics" v-if="iter.metrics">
                  <span class="timeline-metric">mAP50: {{ iter.metrics.map50 ? (iter.metrics.map50 * 100).toFixed(1) + '%' : '-' }}</span>
                  <span class="timeline-metric">mAP95: {{ iter.metrics.map50_95 ? (iter.metrics.map50_95 * 100).toFixed(1) + '%' : '-' }}</span>
                  <span class="timeline-metric">P: {{ iter.metrics.precision ? (iter.metrics.precision * 100).toFixed(1) + '%' : '-' }}</span>
                  <span class="timeline-metric">R: {{ iter.metrics.recall ? (iter.metrics.recall * 100).toFixed(1) + '%' : '-' }}</span>
                </div>
                <div class="timeline-config" v-if="iter.config">
                  <span class="config-label">参数调整:</span>
                  <span class="config-value">
                    {{ iter.config.yolo_model || 'yolov8' }} /
                    {{ iter.config.epochs || 100 }} epochs /
                    batch {{ iter.config.batch_size || 16 }}
                  </span>
                </div>
                <div class="timeline-analysis" v-if="iter.analysis">
                  <span class="analysis-label">Agent 分析:</span>
                  <span class="analysis-text">{{ iter.analysis }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Agent 思考台 -->
        <div class="agent-thoughts-panel">
          <div class="panel-header">
            <h3 class="section-title">
              <span class="section-icon">🧠</span>
              Agent 思考台
            </h3>
            <div class="live-indicator" v-if="selectedTask.status === 'training'">
              <span class="live-dot"></span>
              <span class="live-text">实时思考中</span>
            </div>
          </div>

          <div class="thoughts-scroll" ref="thoughtsContainer">
            <div v-if="agentThoughts.length === 0 && selectedTask.status === 'pending'" class="thoughts-empty">
              <span class="empty-icon">💭</span>
              <p>Agent 尚未开始思考</p>
              <p class="empty-hint">点击"启动"按钮，让 Agent 开始自动训练</p>
            </div>
            <div
              v-for="(thought, i) in agentThoughts"
              :key="i"
              class="thought-item"
              :class="'thought-' + thought.type"
            >
              <div class="thought-header">
                <span class="thought-ts">{{ thought.timestamp }}</span>
                <span class="thought-badge" :class="'thought-badge-' + thought.type">
                  {{ thought.type === 'thought' ? '💭 思考' :
                     thought.type === 'metrics' ? '📊 指标' :
                     thought.type === 'success' ? '✅ 成功' :
                     thought.type === 'warning' ? '⚠️ 警告' :
                     thought.type === 'start' ? '🚀 开始' :
                     thought.type === 'decision' ? '🤔 决策' : '📝 日志' }}
                </span>
              </div>
              <div class="thought-content">{{ thought.content }}</div>
            </div>
          </div>
        </div>

        <!-- 原始日志 -->
        <div class="logs-panel">
          <el-collapse>
            <el-collapse-item title="📄 原始训练日志" name="logs">
              <div class="logs-container" ref="logsContainer">
                <pre>{{ trainingLogs || '暂无日志' }}</pre>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showDetailDialog = false">关闭</el-button>
          <el-button
            v-if="selectedTask && (selectedTask.status === 'pending' || selectedTask.status === 'stopped')"
            type="success"
            size="large"
            @click="startTask(selectedTask)"
          >
            ▶ 启动 Agent 训练
          </el-button>
          <el-button
            v-if="selectedTask && selectedTask.status === 'training'"
            type="danger"
            @click="stopTask(selectedTask)"
          >
            ■ 停止训练
          </el-button>
          <el-button
            v-if="selectedTask && selectedTask.status === 'completed'"
            type="success"
            @click="goToModel(selectedTask)"
          >
            🤖 查看训练好的模型
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const API_BASE = '/api'

export default {
  name: 'TasksView',
  setup() {
    const router = useRouter()
    const tasks = ref([])
    const showCreateDialog = ref(false)
    const showDetailDialog = ref(false)
    const selectedTask = ref(null)
    const creating = ref(false)
    const loading = ref(false)
    const trainingLogs = ref('')
    const iterations = ref([])
    const logsContainer = ref(null)
    const thoughtsContainer = ref(null)
    const metricsCanvas = ref(null)
    const agentCurrentAction = ref('分析训练数据...')

    let pollInterval = null
    let eventSource = null

    const maxIterations = ref(4)

    const newTask = ref({
      name: '',
      description: '',
      class_names: ['person', 'helmet'],
      data_path: '',
      epochs: 100,
    })

    // 计算正在训练的任务
    const trainingTasks = computed(() => tasks.value.filter(t => t.status === 'training'))

    // 当前迭代数
    const currentIteration = computed(() => iterations.value.length || 1)

    // 训练流程步骤
    const trainingFlowSteps = computed(() => {
      if (trainingTasks.value.length === 0) return []
      const task = trainingTasks.value[0]
      const stepIndex = Math.floor((task.progress || 0) / 20)
      return [
        { icon: '📊', label: '数据分析', active: stepIndex >= 0, completed: stepIndex > 0 },
        { icon: '🎯', label: '参数调优', active: stepIndex >= 1, completed: stepIndex > 1 },
        { icon: '🏋️', label: '模型训练', active: stepIndex >= 2, completed: stepIndex > 2 },
        { icon: '📈', label: '效果评估', active: stepIndex >= 3, completed: stepIndex > 3 },
        { icon: '🤔', label: '决策判断', active: stepIndex >= 4, completed: false },
      ]
    })

    // 加载任务列表
    const fetchTasks = async () => {
      try {
        const res = await fetch(`${API_BASE}/tasks/`)
        if (!res.ok) throw new Error('API 请求失败')
        const data = await res.json()
        tasks.value = data.tasks || []
      } catch (e) {
        console.error('获取任务列表失败:', e)
      }
    }

    // 创建任务
    const createTask = async () => {
      if (!newTask.value.description) {
        ElMessage.warning('请填写任务描述')
        return
      }
      if (newTask.value.class_names.length === 0) {
        ElMessage.warning('请至少选择一个检测类别')
        return
      }

      creating.value = true
      try {
        const res = await fetch(`${API_BASE}/tasks/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newTask.value),
        })
        if (!res.ok) throw new Error('创建任务失败')
        const data = await res.json()
        if (data.task_id) {
          ElMessage.success('任务创建成功！')
          showCreateDialog.value = false
          newTask.value = { name: '', description: '', class_names: ['person', 'helmet'], data_path: '', epochs: 100 }
          await fetchTasks()
        }
      } catch (e) {
        ElMessage.error('创建任务失败: ' + e.message)
      } finally {
        creating.value = false
      }
    }

    // 启动训练
    const startTask = async (task) => {
      try {
        const res = await fetch(`${API_BASE}/tasks/${task.task_id}/start`, { method: 'POST' })
        if (!res.ok) throw new Error('启动训练失败')
        const data = await res.json()
        if (data.success) {
          ElMessage.success('Agent 训练流程已启动，正在迭代优化中...')
          await fetchTasks()
          if (showDetailDialog.value) {
            viewDetail(task)
          }
        }
      } catch (e) {
        ElMessage.error('启动训练失败: ' + e.message)
      }
    }

    // 停止训练
    const stopTask = async (task) => {
      try {
        const res = await fetch(`${API_BASE}/tasks/${task.task_id}/stop`, { method: 'POST' })
        if (!res.ok) throw new Error('停止训练失败')
        const data = await res.json()
        if (data.success) {
          ElMessage.success('训练已停止')
          await fetchTasks()
        }
      } catch (e) {
        ElMessage.error('停止训练失败: ' + e.message)
      }
    }

    // 查看详情 - 带错误处理
    const viewDetail = async (task) => {
      selectedTask.value = task
      showDetailDialog.value = true
      trainingLogs.value = ''
      iterations.value = []
      agentCurrentAction.value = '加载任务数据...'

      try {
        await fetchLogs(task.task_id)
        await fetchIterations(task.task_id)
        await nextTick()
        drawMetricsChart()

        if (task.status === 'training') {
          agentCurrentAction.value = '启动实时监控...'
          startSSE(task.task_id)
        }
      } catch (e) {
        console.error('加载详情失败:', e)
        ElMessage.error('加载详情失败: ' + e.message)
      }
    }

    // 行点击处理
    const handleRowClick = (row) => {
      viewDetail(row)
    }

    // 获取日志
    const fetchLogs = async (taskId) => {
      try {
        const res = await fetch(`${API_BASE}/tasks/${taskId}/logs?lines=500`)
        if (!res.ok) throw new Error('获取日志失败')
        const data = await res.json()
        trainingLogs.value = (data.logs || []).map(l => {
          const t = l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : ''
          return `[${t}] ${l.message}`
        }).join('\n')
        scrollLogsToBottom()
      } catch (e) {
        console.error('获取日志失败:', e)
        trainingLogs.value = '无法加载日志: ' + e.message
      }
    }

    // 获取迭代历史
    const fetchIterations = async (taskId) => {
      try {
        const res = await fetch(`${API_BASE}/tasks/${taskId}/iterations`)
        if (!res.ok) throw new Error('获取迭代历史失败')
        const data = await res.json()
        iterations.value = data.iterations || []
      } catch (e) {
        console.error('获取迭代历史失败:', e)
        iterations.value = []
      }
    }

    // 滚动日志到底部
    const scrollLogsToBottom = async () => {
      await nextTick()
      if (logsContainer.value) {
        logsContainer.value.scrollTop = logsContainer.value.scrollHeight
      }
      if (thoughtsContainer.value) {
        thoughtsContainer.value.scrollTop = thoughtsContainer.value.scrollHeight
      }
    }

    // SSE 实时流
    const startSSE = (taskId) => {
      stopSSE()
      agentCurrentAction.value = '连接实时流...'
      eventSource = new EventSource(`${API_BASE}/tasks/${taskId}/stream`)

      eventSource.addEventListener('connected', () => {
        agentCurrentAction.value = '正在分析训练数据...'
      })

      eventSource.addEventListener('log', (e) => {
        const entry = JSON.parse(e.data)
        const ts = entry.ts || new Date().toLocaleTimeString()
        trainingLogs.value += `[${ts}] ${entry.message}\n`
        scrollLogsToBottom()
        // 根据日志内容更新 Agent 动作
        if (entry.message.includes('训练') || entry.message.includes('epoch')) {
          agentCurrentAction.value = '监督模型训练中...'
        } else if (entry.message.includes('评估') || entry.message.includes('mAP')) {
          agentCurrentAction.value = '分析训练效果...'
        } else if (entry.message.includes('调整') || entry.message.includes('参数')) {
          agentCurrentAction.value = '调整训练参数...'
        } else if (entry.message.includes('达标') || entry.message.includes('完成')) {
          agentCurrentAction.value = '评估最终效果...'
        }
      })

      eventSource.addEventListener('metrics', (e) => {
        const m = JSON.parse(e.data)
        selectedTask.value = {
          ...selectedTask.value,
          progress: m.progress,
          map50: m.map50,
          map50_95: m.map50_95,
          precision: m.precision,
          recall: m.recall,
          train_loss: m.train_loss,
          val_loss: m.val_loss,
        }
        agentCurrentAction.value = '计算性能指标...'

        const iterIdx = iterations.value.findIndex(i => i.iteration === m.iteration)
        if (iterIdx >= 0) {
          iterations.value[iterIdx] = { ...iterations.value[iterIdx], ...m }
        } else {
          iterations.value.push({
            iteration: m.iteration,
            iteration_id: `iter_${m.iteration}`,
            status: 'completed',
            metrics: {
              map50: m.map50,
              map50_95: m.map50_95,
              precision: m.precision,
              recall: m.recall,
            }
          })
        }
        // Debounce canvas redraws to avoid excessive rendering during rapid metric updates
        clearTimeout(drawMetricsChart._timer)
        drawMetricsChart._timer = setTimeout(() => drawMetricsChart(), 300)
      })

      eventSource.addEventListener('status', (e) => {
        const s = JSON.parse(e.data)
        selectedTask.value = { ...selectedTask.value, status: s.status }
        if (s.progress !== undefined) selectedTask.value.progress = s.progress
        if (s.status === 'completed') {
          agentCurrentAction.value = '训练完成!'
        } else if (s.status === 'failed') {
          agentCurrentAction.value = '训练遇到问题'
        }
        if (s.status === 'completed' || s.status === 'failed' || s.status === 'stopped') {
          stopSSE()
        }
      })

      eventSource.addEventListener('end', () => {
        stopSSE()
        fetchLogs(taskId)
        fetchIterations(taskId)
      })

      eventSource.addEventListener('heartbeat', () => {})
    }

    const stopSSE = () => {
      if (eventSource) {
        eventSource.close()
        eventSource = null
      }
      if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
      }
    }

    // 跳转到模型页
    const goToModel = (task) => {
      showDetailDialog.value = false
      router.push('/models')
    }

    // 格式化时间
    const formatTime = (timeStr) => {
      if (!timeStr) return '-'
      const d = new Date(timeStr)
      return `${d.getMonth()+1}/${d.getDate()} ${d.toLocaleTimeString()}`
    }

    // 格式化时长
    const formatDuration = (startTime) => {
      if (!startTime) return '0s'
      const start = new Date(startTime)
      const now = new Date()
      const seconds = Math.floor((now - start) / 1000)
      if (seconds < 60) return seconds + 's'
      const minutes = Math.floor(seconds / 60)
      if (minutes < 60) return minutes + 'm'
      const hours = Math.floor(minutes / 60)
      return hours + 'h'
    }

    // 状态标签
    const getStatusType = (status) => {
      const types = {
        pending: 'info',
        training: 'primary',
        completed: 'success',
        failed: 'danger',
        stopped: 'warning',
      }
      return types[status] || 'info'
    }

    const getStatusText = (status) => {
      const texts = {
        pending: '待启动',
        training: 'Agent 训练中',
        completed: '已完成',
        failed: '失败',
        stopped: '已停止',
      }
      return texts[status] || status
    }

    const getProgressStatus = (status) => {
      if (status === 'completed') return 'success'
      if (status === 'failed') return 'exception'
      if (status === 'training') return 'primary'
      return null
    }

    // 指标颜色
    const getMetricClass = (value, threshold) => {
      if (!value) return ''
      return value >= threshold ? 'metric-good' : 'metric-bad'
    }

    // 决策文字
    const getDecisionText = (decision) => {
      const texts = {
        pass: '✅ 达标',
        fail_retry: '🔧 调整重试',
        fail_stop: '❌ 失败停止',
        max_iteration: '⚠️ 达到最大迭代',
      }
      return texts[decision] || decision || '进行中'
    }

    // ========== mAP 趋势图 ==========
    const metricsChartData = computed(() => {
      const labels = []
      const map50Data = []
      const map95Data = []
      const precisionData = []
      const recallData = []
      for (const it of iterations.value) {
        if (it.metrics) {
          const label = it.iteration_id ? it.iteration_id.split('_').pop() : labels.length + 1
          labels.push(label)
          map50Data.push(it.metrics.map50 != null ? it.metrics.map50 * 100 : null)
          map95Data.push(it.metrics.map50_95 != null ? it.metrics.map50_95 * 100 : null)
          precisionData.push(it.metrics.precision != null ? it.metrics.precision * 100 : null)
          recallData.push(it.metrics.recall != null ? it.metrics.recall * 100 : null)
        }
      }
      return { labels, map50Data, map95Data, precisionData, recallData }
    })

    const drawMetricsChart = () => {
      const canvas = metricsCanvas.value
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      const dpr = window.devicePixelRatio || 1
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * dpr
      canvas.height = 200 * dpr
      ctx.scale(dpr, dpr)
      const W = rect.width
      const H = 200

      const data = metricsChartData.value
      if (data.labels.length === 0) return

      const allValues = [
        ...data.map50Data.filter(v => v != null),
        ...data.map95Data.filter(v => v != null),
        ...data.precisionData.filter(v => v != null),
        ...data.recallData.filter(v => v != null),
      ]
      if (allValues.length === 0) return

      const maxVal = Math.max(...allValues, 100) * 1.05
      const minVal = Math.max(0, Math.min(...allValues) * 0.9)
      const padL = 40, padR = 20, padT = 15, padB = 30
      const chartW = W - padL - padR
      const chartH = H - padT - padB

      ctx.clearRect(0, 0, W, H)
      ctx.fillStyle = '#fafafa'
      ctx.fillRect(0, 0, W, H)

      const ySteps = 5
      ctx.strokeStyle = '#e4e7ed'
      ctx.lineWidth = 0.5
      ctx.font = '10px sans-serif'
      ctx.fillStyle = '#999'
      ctx.textAlign = 'right'
      for (let i = 0; i <= ySteps; i++) {
        const y = padT + chartH - (i / ySteps) * chartH
        const val = minVal + (i / ySteps) * (maxVal - minVal)
        ctx.beginPath()
        ctx.moveTo(padL, y)
        ctx.lineTo(padL + chartW, y)
        ctx.stroke()
        ctx.fillText(val.toFixed(0) + '%', padL - 4, y + 3)
      }

      ctx.textAlign = 'center'
      const step = Math.max(1, Math.floor(data.labels.length / 8))
      for (let i = 0; i < data.labels.length; i++) {
        if (i % step !== 0 && i !== data.labels.length - 1) continue
        const x = padL + (i / (Math.max(data.labels.length - 1, 1)) * chartW)
        ctx.fillText('I' + (i + 1), x, H - 5)
      }

      const series = [
        { key: 'map50Data', color: '#67c23a', label: 'mAP@50' },
        { key: 'map95Data', color: '#e6a23c', label: 'mAP@95' },
        { key: 'precisionData', color: '#409eff', label: 'Precision' },
        { key: 'recallData', color: '#f56c6c', label: 'Recall' },
      ]

      for (const s of series) {
        const vals = data[s.key]
        if (vals.length < 2) continue

        ctx.beginPath()
        ctx.strokeStyle = s.color
        ctx.lineWidth = 2
        ctx.setLineDash([])

        let first = true
        for (let i = 0; i < vals.length; i++) {
          if (vals[i] == null) continue
          const x = padL + (i / (vals.length - 1)) * chartW
          const y = padT + chartH - ((vals[i] - minVal) / (maxVal - minVal)) * chartH
          if (first) { ctx.moveTo(x, y); first = false }
          else ctx.lineTo(x, y)
        }
        ctx.stroke()

        for (let i = 0; i < vals.length; i++) {
          if (vals[i] == null) continue
          const x = padL + (i / (vals.length - 1)) * chartW
          const y = padT + chartH - ((vals[i] - minVal) / (maxVal - minVal)) * chartH
          ctx.beginPath()
          ctx.arc(x, y, 3, 0, Math.PI * 2)
          ctx.fillStyle = s.color
          ctx.fill()
        }
      }

      ctx.font = '11px sans-serif'
      ctx.textAlign = 'left'
      let legendX = padL + 10
      for (const s of series) {
        if (data[s.key].filter(v => v != null).length === 0) continue
        ctx.fillStyle = s.color
        ctx.fillRect(legendX, 2, 10, 10)
        ctx.fillStyle = '#666'
        ctx.fillText(s.label, legendX + 14, 11)
        legendX += 80
      }
    }

    // 解析日志为 Agent 思考项
    const agentThoughts = computed(() => {
      if (!trainingLogs.value) return []
      const lines = trainingLogs.value.split('\n')
      const thoughts = []
      for (const line of lines) {
        if (!line.trim()) continue
        const tsMatch = line.match(/\[(\d{2}:\d{2}:\d{2})\]/)
        const timestamp = tsMatch ? tsMatch[1] : ''
        let type = 'output'
        let content = line.replace(/^\[[\d:]+\]\s*/, '').trim()
        if (content.startsWith('🔍') || content.startsWith('🤖') || content.startsWith('🔧')) {
          type = 'thought'
        } else if (content.startsWith('📊') && content.includes('mAP')) {
          type = 'metrics'
        } else if (content.startsWith('✅') || content.startsWith('🎉')) {
          type = 'success'
        } else if (content.startsWith('⚠️') || content.startsWith('❌')) {
          type = 'warning'
        } else if (content.startsWith('🚀') && content.includes('Agent')) {
          type = 'start'
        } else if (content.includes('决策') || content.includes('判断')) {
          type = 'decision'
        }
        if (content) {
          thoughts.push({ timestamp, type, content, raw: line })
        }
      }
      return thoughts
    })

    onMounted(() => {
      loading.value = true
      fetchTasks().finally(() => { loading.value = false })
    })

    onUnmounted(() => {
      stopSSE()
    })

    return {
      tasks,
      showCreateDialog,
      showDetailDialog,
      selectedTask,
      creating,
      loading,
      newTask,
      trainingLogs,
      iterations,
      logsContainer,
      thoughtsContainer,
      metricsCanvas,
      trainingTasks,
      trainingFlowSteps,
      currentIteration,
      maxIterations,
      agentCurrentAction,
      createTask,
      startTask,
      stopTask,
      viewDetail,
      handleRowClick,
      goToModel,
      formatTime,
      formatDuration,
      getStatusType,
      getStatusText,
      getProgressStatus,
      getMetricClass,
      getDecisionText,
      agentThoughts,
    }
  }
}
</script>

<style scoped>
.tasks-view {
  padding: 24px;
  background: #f0f2f5;
  min-height: 100%;
}

/* 页面标题区 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  background: white;
  padding: 20px 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.page-title-area h2 {
  margin: 0 0 6px 0;
  font-size: 22px;
  font-weight: 600;
  color: #1a1a2e;
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: #666;
}

.create-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  font-weight: 600;
}

.btn-icon {
  margin-right: 6px;
  font-size: 16px;
}

/* 训练流程图 */
.training-flow-diagram {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: white;
  border-radius: 12px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.flow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  opacity: 0.4;
  transition: all 0.3s;
}

.flow-step.active {
  opacity: 1;
  transform: scale(1.05);
}

.flow-step.completed {
  opacity: 0.8;
}

.flow-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  transition: all 0.3s;
}

.flow-step.active .flow-icon {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.flow-step.completed .flow-icon {
  background: #67c23a;
}

.flow-label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.flow-arrow {
  font-size: 20px;
  color: #ddd;
  margin-top: -20px;
}

/* 任务列表 */
.task-id {
  font-size: 11px;
  color: #999;
}

.task-name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-name {
  font-weight: 500;
}

.agent-tag {
  width: fit-content;
  font-size: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: white;
}

.status-tag-training {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: white;
}

.pulse-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  background: white;
  border-radius: 50%;
  margin-right: 6px;
  animation: pulse 1.5s infinite;
}

.progress-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-text {
  font-size: 12px;
  color: #666;
  min-width: 35px;
}

.metric-value {
  font-weight: 600;
}

.metric-good {
  color: #67c23a;
}

.metric-bad {
  color: #f56c6c;
}

/* ========== 详情对话框 ========== */
.detail-content {
  padding: 0 4px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
}

.detail-status-card {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-badge {
  padding: 8px 16px;
  border-radius: 20px;
  background: rgba(255,255,255,0.2);
  font-weight: 600;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pulse-ring {
  width: 10px;
  height: 10px;
  border: 2px solid white;
  border-radius: 50%;
  animation: pulse-ring 1.5s infinite;
}

@keyframes pulse-ring {
  0% { transform: scale(0.8); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.5; }
  100% { transform: scale(0.8); opacity: 1; }
}

.task-meta {
  display: flex;
  gap: 16px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  opacity: 0.9;
}

.meta-icon {
  font-size: 14px;
}

.agent-indicator {
  background: rgba(255,255,255,0.15);
  padding: 12px 20px;
  border-radius: 10px;
}

.agent-thinking {
  display: flex;
  align-items: center;
  gap: 12px;
}

.thinking-icon {
  font-size: 28px;
  animation: bounce 1s infinite;
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

.thinking-text {
  display: flex;
  flex-direction: column;
}

.thinking-label {
  font-size: 11px;
  opacity: 0.8;
}

.thinking-action {
  font-size: 14px;
  font-weight: 600;
}

/* 指标仪表板 */
.metrics-dashboard {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.metric-gauge {
  background: white;
  padding: 16px;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.gauge-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.gauge-title {
  font-weight: 600;
  font-size: 13px;
  color: #333;
}

.gauge-target {
  font-size: 11px;
  color: #999;
}

.gauge-bar {
  height: 8px;
  background: #f0f2f5;
  border-radius: 4px;
  position: relative;
  overflow: hidden;
}

.gauge-fill {
  height: 100%;
  background: linear-gradient(90deg, #67c23a 0%, #85ce61 100%);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.gauge-fill.map95 {
  background: linear-gradient(90deg, #e6a23c 0%, #ebb563 100%);
}

.gauge-fill.precision {
  background: linear-gradient(90deg, #409eff 0%, #66b1ff 100%);
}

.gauge-fill.recall {
  background: linear-gradient(90deg, #f56c6c 0%, #f78989 100%);
}

.gauge-marker {
  position: absolute;
  top: -2px;
  width: 2px;
  height: 12px;
  background: #f56c6c;
  border-radius: 1px;
}

.gauge-value {
  text-align: right;
  font-size: 20px;
  font-weight: 700;
  margin-top: 8px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px 0;
  font-size: 15px;
  font-weight: 600;
  color: #1a1a2e;
}

.section-icon {
  font-size: 18px;
}

/* Agent 决策流程时间线 */
.agent-timeline {
  background: white;
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.timeline {
  position: relative;
  padding-left: 40px;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: linear-gradient(to bottom, #667eea, #764ba2);
}

.timeline-item {
  position: relative;
  padding-bottom: 20px;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-marker {
  position: absolute;
  left: -40px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f0f2f5;
  border: 3px solid #667eea;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  z-index: 1;
}

.timeline-item.completed .timeline-marker {
  background: #67c23a;
  border-color: #67c23a;
}

.timeline-item.current .timeline-marker {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-color: #667eea;
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.2);
}

.marker-number {
  font-weight: 600;
  color: #667eea;
}

.timeline-content {
  background: #f8f9fa;
  padding: 12px 16px;
  border-radius: 8px;
}

.timeline-item.current .timeline-content {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border: 1px solid rgba(102, 126, 234, 0.2);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.iteration-label {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.decision-tag {
  font-size: 11px;
}

.timeline-metrics {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.timeline-metric {
  font-size: 12px;
  color: #666;
}

.timeline-config {
  font-size: 12px;
  color: #999;
}

.config-label {
  color: #667eea;
  font-weight: 500;
}

.timeline-analysis {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e6e6e6;
}

.analysis-label {
  font-size: 12px;
  color: #667eea;
  font-weight: 500;
}

.analysis-text {
  font-size: 12px;
  color: #666;
  margin-left: 6px;
}

/* Agent 思考台 */
.agent-thoughts-panel {
  background: white;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(103, 194, 58, 0.1);
  border-radius: 20px;
}

.live-dot {
  width: 8px;
  height: 8px;
  background: #67c23a;
  border-radius: 50%;
  animation: pulse 1.5s infinite;
}

.live-text {
  font-size: 12px;
  color: #67c23a;
  font-weight: 500;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.thoughts-scroll {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border: 1px solid #e6e6e6;
  border-radius: 10px;
  padding: 12px;
  max-height: 300px;
  overflow-y: auto;
}

.thoughts-empty {
  text-align: center;
  padding: 40px;
  color: #999;
}

.empty-icon {
  font-size: 40px;
  display: block;
  margin-bottom: 12px;
}

.empty-hint {
  font-size: 12px;
  margin-top: 8px;
}

.thought-item {
  background: white;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  border-left: 4px solid #ddd;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.thought-thought { border-left-color: #9c27b0; }
.thought-metrics { border-left-color: #2196f3; }
.thought-success { border-left-color: #4caf50; }
.thought-warning { border-left-color: #ff9800; }
.thought-start { border-left-color: #00bcd4; }
.thought-decision { border-left-color: #ff5722; }
.thought-output { border-left-color: #9e9e9e; }

.thought-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}

.thought-ts {
  font-size: 11px;
  color: #999;
  font-family: 'Consolas', monospace;
}

.thought-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
  color: white;
}

.thought-badge-thought { background: #9c27b0; }
.thought-badge-metrics { background: #2196f3; }
.thought-badge-success { background: #4caf50; }
.thought-badge-warning { background: #ff9800; }
.thought-badge-start { background: #00bcd4; }
.thought-badge-decision { background: #ff5722; }
.thought-badge-output { background: #9e9e9e; }

.thought-content {
  font-size: 13px;
  color: #333;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 日志面板 */
.logs-panel {
  margin-top: 16px;
}

.logs-container {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 15px;
  border-radius: 4px;
  max-height: 250px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.logs-container pre {
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

/* 对话框底部 */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.text-muted {
  color: #999;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
</style>
