<template>
  <div class="models-view">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="section-title">模型中心</h2>
      </div>
      <el-button @click="loadModels">
        🔄 刷新
      </el-button>
    </div>

    <!-- Models List -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <div v-else-if="models.length === 0">
      <EmptyState
        icon="🤖"
        title="暂无模型"
        description="完成训练任务后，模型将显示在这里"
      >
        <el-button type="primary" @click="$router.push('/tasks')" style="margin-top: 16px">
          去训练
        </el-button>
      </EmptyState>
    </div>

    <div v-else class="models-grid">
      <div v-for="model in models" :key="model.task_id" class="model-card">
        <div class="model-card-header">
          <div class="model-icon">🤖</div>
          <div class="model-info">
            <h3 class="model-name">{{ model.name || model.task_id }}</h3>
            <span class="model-type">{{ model.model_type || 'YOLOv8' }}</span>
          </div>
          <StatusBadge :status="model.is_deployed ? 'deployed' : 'stopped'" />
        </div>

        <div class="model-stats">
          <div class="stat-item">
            <span class="stat-label">mAP@50</span>
            <span class="stat-value" :class="mapClass(model.map50)">
              {{ model.map50 ? (model.map50 * 100).toFixed(1) + '%' : '-' }}
            </span>
          </div>
          <div class="stat-item">
            <span class="stat-label">mAP</span>
            <span class="stat-value">
              {{ model.map50_95 ? (model.map50_95 * 100).toFixed(1) + '%' : '-' }}
            </span>
          </div>
          <div class="stat-item">
            <span class="stat-label">大小</span>
            <span class="stat-value">{{ formatSize(model.file_size) }}</span>
          </div>
        </div>

        <div class="model-actions">
          <el-button
            v-if="!model.is_deployed"
            type="primary"
            size="small"
            :loading="deployingId === model.task_id"
            @click="deployModel(model)"
          >
            部署
          </el-button>
          <el-button
            v-else
            type="warning"
            size="small"
            :loading="deployingId === model.task_id"
            @click="undeployModel(model)"
          >
            取消部署
          </el-button>
          <el-button size="small" @click="openInferDialog(model)">
            测试推理
          </el-button>
          <el-dropdown trigger="click" @command="(cmd) => exportModel(model, cmd)">
            <el-button size="small">
              导出 ▾
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="onnx">ONNX</el-dropdown-item>
                <el-dropdown-item command="torchscript">TorchScript</el-dropdown-item>
                <el-dropdown-item command="tflite">TFLite</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

    <!-- Inference Dialog -->
    <el-dialog
      v-model="showInferDialog"
      :title="`推理测试 - ${selectedModel?.name || ''}`"
      width="800px"
      destroy-on-close
    >
      <div class="infer-content" v-if="selectedModel">
        <el-tabs v-model="inferTab">
          <!-- URL Mode -->
          <el-tab-pane label="图片URL" name="url">
            <el-input
              v-model="inferUrl"
              placeholder="输入图片URL，多个用换行分隔"
              type="textarea"
              :rows="4"
              style="margin-bottom: 12px"
            />
            <el-button type="primary" :loading="inferring" @click="runInferUrl">
              执行推理
            </el-button>
          </el-tab-pane>

          <!-- Upload Mode -->
          <el-tab-pane label="上传图片" name="upload">
            <el-upload
              ref="inferUploadRef"
              drag
              :auto-upload="false"
              :limit="1"
              :on-change="(f) => inferFile = f.raw"
              accept="image/*"
              style="width: 100%; margin-bottom: 12px"
            >
              <div class="upload-hint">
                <div class="upload-icon">🖼</div>
                <div>点击或拖拽上传图片</div>
              </div>
            </el-upload>
            <el-button type="primary" :loading="inferring" :disabled="!inferFile" @click="runInferFile">
              执行推理
            </el-button>
          </el-tab-pane>
        </el-tabs>

        <!-- Results -->
        <div v-if="inferResults.length" class="infer-results">
          <h4>检测结果</h4>
          <div class="results-count">
            共 {{ totalDetections }} 个检测目标
          </div>
          <div class="results-grid">
            <div
              v-for="(r, i) in inferResults"
              :key="i"
              class="infer-result"
            >
              <img v-if="r.image_url" :src="r.image_url" class="result-img" />
              <div class="result-dets" v-if="r.detections?.length">
                <div
                  v-for="(d, j) in r.detections"
                  :key="j"
                  class="det-item"
                >
                  <span class="det-class">{{ d.class }}</span>
                  <span class="det-conf">{{ (d.confidence * 100).toFixed(0) }}%</span>
                </div>
              </div>
              <div v-else class="no-dets">未检测到目标</div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import StatusBadge from '../components/common/StatusBadge.vue'
import EmptyState from '../components/common/EmptyState.vue'
import { getModels, deployModel as apiDeploy, undeployModel as apiUndeploy, inferModel, inferModelImage } from '../api/models'

const models = ref([])
const loading = ref(false)
const deployingId = ref(null)
const showInferDialog = ref(false)
const selectedModel = ref(null)
const inferTab = ref('url')
const inferUrl = ref('')
const inferFile = ref(null)
const inferring = ref(false)
const inferResults = ref([])

async function loadModels() {
  loading.value = true
  try {
    const data = await getModels()
    models.value = data.models || []
  } catch (e) {
    ElMessage.error('加载模型失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function deployModel(model) {
  deployingId.value = model.task_id
  try {
    await apiDeploy(model.task_id)
    ElMessage.success('模型已部署')
    await loadModels()
  } catch (e) {
    ElMessage.error('部署失败: ' + e.message)
  } finally {
    deployingId.value = null
  }
}

async function undeployModel(model) {
  deployingId.value = model.task_id
  try {
    await apiUndeploy(model.task_id)
    ElMessage.success('已取消部署')
    await loadModels()
  } catch (e) {
    ElMessage.error('取消部署失败: ' + e.message)
  } finally {
    deployingId.value = null
  }
}

function openInferDialog(model) {
  selectedModel.value = model
  showInferDialog.value = true
  inferResults.value = []
  inferUrl.value = ''
  inferFile.value = null
}

async function runInferUrl() {
  if (!inferUrl.value.trim()) {
    ElMessage.warning('请输入图片URL')
    return
  }
  inferring.value = true
  inferResults.value = []
  try {
    const urls = inferUrl.value.split('\n').map(s => s.trim()).filter(Boolean)
    const data = await inferModel(selectedModel.value.task_id, { images: urls })
    if (data.results) {
      inferResults.value = data.results
    } else {
      ElMessage.warning('未返回检测结果')
    }
  } catch (e) {
    ElMessage.error('推理失败: ' + e.message)
  } finally {
    inferring.value = false
  }
}

async function runInferFile() {
  if (!inferFile.value) {
    ElMessage.warning('请选择图片')
    return
  }
  inferring.value = true
  inferResults.value = []
  try {
    const data = await inferModelImage(selectedModel.value.task_id, inferFile.value)
    if (data.results) {
      inferResults.value = data.results
    } else {
      ElMessage.warning('未返回检测结果')
    }
  } catch (e) {
    ElMessage.error('推理失败: ' + e.message)
  } finally {
    inferring.value = false
  }
}

async function exportModel(model, format) {
  ElMessage.info(`正在导出 ${format.toUpperCase()} 格式...`)
  try {
    await window.open(`/api/models/${model.task_id}/export?format=${format}`, '_blank')
  } catch (e) {
    ElMessage.error('导出失败: ' + e.message)
  }
}

function mapClass(val) {
  if (!val) return ''
  return val >= 0.82 ? 'metric-good' : 'metric-bad'
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const totalDetections = 0

onMounted(loadModels)
</script>

<style scoped>
.models-view {
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
}

/* Loading */
.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-12);
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

/* Models Grid */
.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}

.model-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.model-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.model-icon {
  font-size: var(--text-2xl);
}

.model-info {
  flex: 1;
}

.model-name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--color-text);
  margin-bottom: 2px;
}

.model-type {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.model-stats {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-3);
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-4);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.stat-value {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
}

.metric-good { color: var(--color-secondary); }
.metric-bad { color: var(--color-danger); }

.model-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

/* Inference */
.upload-hint {
  padding: var(--space-6);
  text-align: center;
}

.upload-icon {
  font-size: 36px;
  margin-bottom: var(--space-2);
}

.infer-results {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.infer-results h4 {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  margin-bottom: var(--space-3);
}

.results-count {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  margin-bottom: var(--space-3);
}

.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--space-3);
}

.infer-result {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.result-img {
  width: 100%;
  height: 140px;
  object-fit: cover;
  background: var(--color-surface-2);
}

.result-dets {
  padding: var(--space-2);
}

.det-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
  font-size: var(--text-xs);
}

.det-class {
  font-weight: var(--font-medium);
}

.det-conf {
  color: var(--color-secondary);
}

.no-dets {
  padding: var(--space-3);
  text-align: center;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
</style>
