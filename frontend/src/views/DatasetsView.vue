<template>
  <div class="datasets-view">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="section-title">数据集管理</h2>
      </div>
      <div class="header-actions">
        <el-button @click="showUploadDialog = true">+ 上传图片</el-button>
      </div>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" class="main-tabs">
      <!-- Browse Tab -->
      <el-tab-pane label="浏览图片" name="browse">
        <div class="browse-panel">
          <!-- Stats -->
          <div class="stats-row" v-if="currentDataset">
            <div class="stat-pill">
              <span class="stat-icon">🖼</span>
              <span>{{ currentDataset.total_images || 0 }} 张图片</span>
            </div>
            <div class="stat-pill success">
              <span class="stat-icon">✓</span>
              <span>{{ currentDataset.annotated_images || 0 }} 已标注</span>
            </div>
          </div>

          <!-- Image Grid -->
          <div v-if="loadingImages" class="loading-state">
            <div class="spinner"></div>
          </div>

          <div v-else-if="images.length === 0">
            <EmptyState
              icon="📁"
              title="暂无图片"
              description="上传图片或使用自动标注功能"
            />
          </div>

          <div v-else class="image-grid">
            <div
              v-for="img in images"
              :key="img.id"
              class="image-card"
              @click="openImage(img)"
            >
              <div class="image-thumb">
                <img :src="img.url" :alt="img.filename" @error="onImgError" />
                <span class="obj-badge" v-if="img.box_count">{{ img.box_count }} 对象</span>
              </div>
              <div class="image-name">{{ img.filename }}</div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Auto-label Tab -->
      <el-tab-pane label="自动标注" name="autolabel">
        <div class="autolabel-panel">
          <el-alert type="info" :closable="false" class="info-alert">
            <p>上传图片后，输入要检测的类别名称，AI 将自动进行目标检测标注。</p>
            <p>支持 Grounding DINO + SAM 组合，或 YOLOv8 回退模式。</p>
          </el-alert>

          <div class="autolabel-form">
            <el-form label-position="top">
              <el-form-item label="数据集">
                <el-select v-model="autoLabelDatasetId" style="width: 100%">
                  <el-option
                    v-for="ds in datasets"
                    :key="ds.id"
                    :label="ds.name"
                    :value="ds.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="检测任务描述">
                <el-input
                  v-model="autoLabelTask"
                  placeholder="例如：检测未佩戴安全帽和手套的工人"
                />
              </el-form-item>
              <el-form-item label="检测类别（逗号分隔）">
                <el-input
                  v-model="autoLabelClasses"
                  placeholder="未戴安全帽, 未戴手套, 火灾"
                />
              </el-form-item>
            </el-form>

            <el-button
              type="primary"
              :loading="autoLabelRunning"
              :disabled="!autoLabelClasses || !autoLabelTask"
              @click="runAutoLabel"
              style="width: 100%"
            >
              {{ autoLabelRunning ? '标注中...' : '开始自动标注' }}
            </el-button>
          </div>

          <!-- Auto-label Results -->
          <div v-if="autoLabelResults.length" class="results-section">
            <div class="results-header">
              <h4>标注结果</h4>
              <el-button size="small" @click="applyAutoLabelResults">
                应用到数据集
              </el-button>
            </div>
            <div class="results-count">
              共 {{ autoLabelResults.length }} 个检测结果
            </div>
            <div class="results-preview">
              <div
                v-for="(r, i) in autoLabelResults.slice(0, 20)"
                :key="i"
                class="result-chip"
              >
                <span class="chip-class">{{ r.class_name }}</span>
                <span class="chip-conf">{{ (r.confidence * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- Upload Dialog -->
    <el-dialog v-model="showUploadDialog" title="上传图片" width="480px" destroy-on-close>
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :limit="100"
        :on-change="onFileChange"
        :on-remove="onFileRemove"
        multiple
        accept="image/*"
        style="width: 100%"
      >
        <div class="upload-content">
          <div class="upload-icon">📤</div>
          <div class="upload-text">拖拽图片到此处，或点击上传</div>
          <div class="upload-hint">支持 JPG、PNG、WebP，单个文件不超过 10MB</div>
        </div>
      </el-upload>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">
          上传 {{ fileList.length }} 张
        </el-button>
      </template>
    </el-dialog>

    <!-- Image Detail Dialog -->
    <el-dialog
      v-model="showImageDialog"
      :title="selectedImage?.filename"
      width="900px"
      destroy-on-close
    >
      <div class="image-detail" v-if="selectedImage">
        <div class="detail-image-panel">
          <div class="canvas-wrapper">
            <img
              ref="detailImgRef"
              :src="selectedImage.url"
              class="detail-img"
              @load="onImageLoad"
              crossorigin="anonymous"
            />
            <canvas ref="bboxCanvas" class="bbox-canvas"></canvas>
          </div>
        </div>
        <div class="detail-info-panel">
          <h4>检测结果</h4>
          <div class="bbox-list" v-if="selectedImage.boxes?.length">
            <div
              v-for="(box, i) in selectedImage.boxes"
              :key="i"
              class="bbox-item"
              @mouseenter="highlightBbox(i)"
              @mouseleave="unhighlightBbox"
            >
              <div class="bbox-color" :style="{ background: getBboxColor(i) }"></div>
              <div class="bbox-info">
                <span class="bbox-class">{{ box.class_name }}</span>
                <span class="bbox-coords">
                  {{ box.bbox.map(v => v.toFixed(3)).join(', ') }}
                </span>
              </div>
            </div>
          </div>
          <div v-else class="no-bbox">无检测结果</div>

          <h4 style="margin-top: 16px">YOLO 格式</h4>
          <div class="yolo-code">
            <pre>{{ getYoloFormat(selectedImage) }}</pre>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showImageDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import EmptyState from '../components/common/EmptyState.vue'
import { getDatasets, getDatasetImages, uploadImages, autoLabelDinoSam, getAutoLabelInfo } from '../api/datasets'

const COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']

// State
const activeTab = ref('browse')
const datasets = ref([])
const currentDatasetId = ref('demo')
const images = ref([])
const loadingImages = ref(false)
const showUploadDialog = ref(false)
const showImageDialog = ref(false)
const selectedImage = ref(null)
const fileList = ref([])
const uploading = ref(false)

// Auto-label
const autoLabelTask = ref('')
const autoLabelClasses = ref('')
const autoLabelDatasetId = ref('demo')
const autoLabelRunning = ref(false)
const autoLabelResults = ref([])

// Image detail refs
const detailImgRef = ref(null)
const bboxCanvas = ref(null)
const highlightedBbox = ref(-1)

const currentDataset = computed(() =>
  datasets.value.find(d => d.id === currentDatasetId.value) || {}
)

async function loadDatasets() {
  try {
    const data = await getDatasets()
    datasets.value = data.datasets || []
    if (datasets.value.length && !currentDatasetId.value) {
      currentDatasetId.value = datasets.value[0].id
    }
  } catch (e) {
    // Try demo
    datasets.value = [{ id: 'demo', name: '演示数据集', total_images: 0, annotated_images: 0 }]
  }
}

async function loadImages() {
  if (!currentDatasetId.value) return
  loadingImages.value = true
  try {
    const data = await getDatasetImages(currentDatasetId.value)
    const imgs = data.images || []
    images.value = imgs.map((img, idx) => ({
      ...img,
      url: `/api/datasets/image/${img.id}`,
      box_count: img.boxes?.length || 0,
    }))
  } catch (e) {
    images.value = []
  } finally {
    loadingImages.value = false
  }
}

async function submitUpload() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择图片')
    return
  }
  uploading.value = true
  try {
    const files = fileList.value.map(f => f.raw)
    await uploadImages(currentDatasetId.value, files)
    ElMessage.success(`成功上传 ${files.length} 张图片`)
    showUploadDialog.value = false
    fileList.value = []
    await loadImages()
  } catch (e) {
    ElMessage.error('上传失败: ' + e.message)
  } finally {
    uploading.value = false
  }
}

function onFileChange(file, files) {
  fileList.value = files
}

function onFileRemove(file, files) {
  fileList.value = files
}

async function runAutoLabel() {
  if (!autoLabelClasses.value || !autoLabelTask.value) {
    ElMessage.warning('请填写任务描述和类别')
    return
  }
  autoLabelRunning.value = true
  autoLabelResults.value = []
  try {
    const classList = autoLabelClasses.value.split(',').map(s => s.trim()).filter(Boolean)
    const data = await autoLabelDinoSam({
      task_description: autoLabelTask.value,
      class_names: classList,
      dataset_id: autoLabelDatasetId.value || 'demo',
      box_threshold: 0.25,
    })
    if (data.success) {
      const results = []
      for (const img of data.images || []) {
        for (const box of img.boxes || []) {
          results.push({
            class_id: box.class_id,
            class_name: box.class_name,
            confidence: box.confidence,
            bbox: box.bbox,
          })
        }
      }
      autoLabelResults.value = results
      ElMessage.success(data.message || '标注完成')
      await loadImages()
    } else {
      ElMessage.error(data.message || '标注失败')
    }
  } catch (e) {
    ElMessage.error('标注失败: ' + e.message)
  } finally {
    autoLabelRunning.value = false
  }
}

async function applyAutoLabelResults() {
  ElMessage.success(`已将 ${autoLabelResults.value.length} 个结果应用到数据集`)
  autoLabelResults.value = []
  await loadImages()
}

function openImage(img) {
  selectedImage.value = img
  highlightedBbox.value = -1
  showImageDialog.value = true
  nextTick(() => drawBboxes())
}

function onImageLoad() {
  nextTick(() => drawBboxes())
}

function drawBboxes() {
  const canvas = bboxCanvas.value
  const img = detailImgRef.value
  if (!canvas || !img || !selectedImage.value) return
  const rect = img.getBoundingClientRect()
  canvas.width = rect.width
  canvas.height = rect.height
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  selectedImage.value.boxes?.forEach((box, i) => {
    const color = getBboxColor(i)
    const hl = i === highlightedBbox.value
    const x = (box.bbox[0] - box.bbox[2] / 2) * canvas.width
    const y = (box.bbox[1] - box.bbox[3] / 2) * canvas.height
    const w = box.bbox[2] * canvas.width
    const h = box.bbox[3] * canvas.height
    ctx.strokeStyle = color
    ctx.lineWidth = hl ? 3 : 2
    ctx.globalAlpha = hl ? 1 : 0.8
    ctx.strokeRect(x, y, w, h)
    ctx.globalAlpha = 0.9
    ctx.fillStyle = color
    ctx.fillRect(x, y - 18 > 0 ? y - 18 : 0, ctx.measureText(box.class_name).width + 8, 18)
    ctx.globalAlpha = 1
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 12px sans-serif'
    ctx.fillText(box.class_name, x + 4, y - 5 > 0 ? y - 5 : 12)
  })
  ctx.globalAlpha = 1
}

function highlightBbox(i) {
  highlightedBbox.value = i
  drawBboxes()
}

function unhighlightBbox() {
  highlightedBbox.value = -1
  drawBboxes()
}

function getBboxColor(i) {
  return COLORS[i % COLORS.length]
}

function getYoloFormat(img) {
  return img.boxes?.map(b =>
    `${b.class_id} ${b.bbox.map(v => v.toFixed(6)).join(' ')}`
  ).join('\n') || '# 无标注'
}

function onImgError(e) {
  e.target.style.display = 'none'
}

watch(showImageDialog, (val) => {
  if (val) {
    nextTick(() => window.addEventListener('resize', drawBboxes))
  } else {
    window.removeEventListener('resize', drawBboxes)
  }
})

watch(currentDatasetId, loadImages)

onMounted(async () => {
  await loadDatasets()
  await loadImages()
})
</script>

<style scoped>
.datasets-view {
  max-width: 1200px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-5);
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

/* Tabs */
.main-tabs {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  box-shadow: var(--shadow-sm);
}

/* Browse */
.stats-row {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-2);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.stat-pill.success {
  background: var(--color-secondary-bg);
  color: var(--color-secondary);
}

.stat-icon {
  font-size: var(--text-sm);
}

/* Image Grid */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--space-3);
}

.image-card {
  cursor: pointer;
  border-radius: var(--radius-sm);
  overflow: hidden;
  border: 1px solid var(--color-border);
  transition: all var(--transition-fast);
}

.image-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--color-primary-light);
}

.image-thumb {
  position: relative;
  padding-top: 75%;
  background: var(--color-surface-2);
}

.image-thumb img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.obj-badge {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.image-name {
  padding: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Loading */
.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-8);
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

/* Auto-label */
.info-alert {
  margin-bottom: var(--space-5);
}

.info-alert p {
  margin-bottom: var(--space-1);
  font-size: var(--text-sm);
}

.autolabel-form {
  max-width: 480px;
}

.results-section {
  margin-top: var(--space-5);
  padding: var(--space-4);
  background: var(--color-surface-2);
  border-radius: var(--radius-md);
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.results-header h4 {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
}

.results-count {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  margin-bottom: var(--space-3);
}

.results-preview {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.result-chip {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
}

.chip-class {
  font-weight: var(--font-medium);
}

.chip-conf {
  color: var(--color-secondary);
}

/* Upload */
.upload-content {
  padding: var(--space-8);
  text-align: center;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: var(--space-3);
}

.upload-text {
  font-size: var(--text-md);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.upload-hint {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

/* Image Detail */
.image-detail {
  display: flex;
  gap: var(--space-5);
  height: 60vh;
}

.detail-image-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a1a1a;
  border-radius: var(--radius-md);
  overflow: hidden;
}

.canvas-wrapper {
  position: relative;
  max-width: 100%;
  max-height: 100%;
}

.detail-img {
  max-width: 100%;
  max-height: 55vh;
  display: block;
}

.bbox-canvas {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.detail-info-panel {
  width: 260px;
  overflow-y: auto;
}

.detail-info-panel h4 {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  margin-bottom: var(--space-3);
  color: var(--color-text-secondary);
}

.bbox-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.bbox-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.bbox-item:hover {
  background: var(--color-primary-bg);
}

.bbox-color {
  width: 4px;
  height: 28px;
  border-radius: 2px;
  flex-shrink: 0;
}

.bbox-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.bbox-class {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.bbox-coords {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.no-bbox {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  padding: var(--space-3);
  text-align: center;
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
}

.yolo-code {
  background: #1e1e1e;
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  overflow-x: auto;
}

.yolo-code pre {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: #d4d4d4;
  white-space: pre-wrap;
  margin: 0;
}
</style>
