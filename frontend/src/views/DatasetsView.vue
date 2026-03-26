<template>
  <div class="datasets-view">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="section-title">数据集管理</h2>
        <el-select
          v-model="currentDatasetId"
          placeholder="选择数据集"
          style="width: 200px; margin-left: 16px"
          @change="onDatasetChange"
        >
          <el-option
            v-for="ds in datasets"
            :key="ds.id"
            :label="ds.name"
            :value="ds.id"
          />
        </el-select>
      </div>
      <div class="header-actions">
        <el-button @click="showCreateDialog = true">+ 新建数据集</el-button>
        <el-button @click="loadDatasets" :loading="loadingDatasets">刷新</el-button>
      </div>
    </div>

    <!-- Dataset Cards -->
    <div v-if="loadingDatasets" class="loading-state">
      <div class="spinner"></div>
    </div>

    <div v-else-if="datasets.length === 0" class="empty-datasets">
      <EmptyState
        icon="📁"
        title="暂无数据集"
        description="创建数据集或上传图片开始"
      />
    </div>

    <div v-else class="dataset-cards">
      <div
        v-for="ds in datasets"
        :key="ds.id"
        class="dataset-card"
        :class="{ active: ds.id === currentDatasetId }"
        @click="selectDataset(ds.id)"
      >
        <div class="card-header">
          <span class="card-icon">📁</span>
          <span class="card-name">{{ ds.name }}</span>
          <el-dropdown trigger="click" @command="(cmd) => onDatasetCommand(cmd, ds)" @click.stop>
            <el-button size="small" text>⋮</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="card-stats">
          <div class="stat">
            <span class="stat-num">{{ ds.total_images || 0 }}</span>
            <span class="stat-label">图片</span>
          </div>
          <div class="stat">
            <span class="stat-num">{{ ds.train_count || 0 }}</span>
            <span class="stat-label">训练</span>
          </div>
          <div class="stat">
            <span class="stat-num">{{ ds.val_count || 0 }}</span>
            <span class="stat-label">验证</span>
          </div>
        </div>
        <div class="card-classes" v-if="ds.class_names?.length">
          <span class="class-tag" v-for="c in ds.class_names.slice(0, 3)" :key="c">{{ c }}</span>
          <span v-if="ds.class_names.length > 3" class="class-more">+{{ ds.class_names.length - 3 }}</span>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" class="main-tabs" style="margin-top: 20px">
      <!-- Browse Tab -->
      <el-tab-pane label="浏览图片" name="browse">
        <div class="browse-panel">
          <!-- Toolbar -->
          <div class="toolbar">
            <div class="toolbar-left">
              <span class="img-count">{{ images.length }} 张图片</span>
            </div>
            <div class="toolbar-right">
              <el-button size="small" @click="showUploadDialog = true">上传图片</el-button>
              <el-button size="small" type="danger" :disabled="!selectedImage" @click="onDeleteImage">
                删除选中
              </el-button>
            </div>
          </div>

          <!-- Image Grid -->
          <div v-if="loadingImages" class="loading-state">
            <div class="spinner"></div>
          </div>

          <div v-else-if="images.length === 0">
            <EmptyState
              icon="🖼"
              title="暂无图片"
              description="上传图片或使用自动标注功能"
            />
          </div>

          <div v-else class="image-grid">
            <div
              v-for="img in images"
              :key="img.id"
              class="image-card"
              :class="{ selected: selectedImage?.id === img.id }"
              @click="openImage(img)"
            >
              <div class="image-thumb">
                <img :src="img.url" :alt="img.filename" @error="onImgError" />
                <span class="obj-badge" v-if="img.num_objects || img.boxes?.length">{{ img.num_objects || img.boxes?.length || 0 }}</span>
                <span class="selected-badge" v-if="selectedImage?.id === img.id">✓</span>
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
            <p>当前模式: <strong>{{ autoLabelMode }}</strong></p>
          </el-alert>

          <!-- Auto-label Info -->
          <div class="service-status" v-if="autoLabelInfo">
            <div class="status-item">
              <span class="status-dot" :class="autoLabelInfo.dino_ok ? 'online' : 'offline'"></span>
              Grounding DINO
            </div>
            <div class="status-item">
              <span class="status-dot" :class="autoLabelInfo.sam_ok ? 'online' : 'offline'"></span>
              SAM
            </div>
            <div class="status-item">
              <span class="status-dot" :class="autoLabelInfo.yolo_fallback ? 'online' : 'offline'"></span>
              YOLOv8 回退
            </div>
          </div>

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
                  placeholder="person, helmet, no_helmet"
                />
              </el-form-item>
            </el-form>

            <!-- Progress -->
            <div v-if="autoLabelRunning" class="progress-section">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: autoLabelProgress + '%' }"></div>
              </div>
              <div class="progress-text">
                标注中... {{ autoLabelAnnotated }}/{{ autoLabelTotal }}
              </div>
            </div>

            <el-button
              type="primary"
              :loading="autoLabelRunning"
              :disabled="!autoLabelClasses || !autoLabelTask || !autoLabelDatasetId"
              @click="runAutoLabel"
              style="width: 100%"
            >
              {{ autoLabelRunning ? '标注中...' : '开始自动标注' }}
            </el-button>
          </div>

          <!-- Auto-label Results -->
          <div v-if="autoLabelResults.length" class="results-section">
            <div class="results-header">
              <h4>标注结果预览</h4>
              <el-button size="small" type="success" @click="applyAutoLabelResults">
                应用到数据集
              </el-button>
            </div>
            <div class="results-count">
              共 {{ autoLabelResults.length }} 个检测结果 ({{ autoLabelMode }})
            </div>
            <div class="results-preview">
              <div
                v-for="(r, i) in autoLabelResults.slice(0, 30)"
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

    <!-- Create Dataset Dialog -->
    <el-dialog v-model="showCreateDialog" title="创建数据集" width="400px">
      <el-form @submit.prevent="onCreateDataset">
        <el-form-item label="数据集名称">
          <el-input v-model="newDatasetName" placeholder="输入数据集名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creatingDataset" @click="onCreateDataset">
          创建
        </el-button>
      </template>
    </el-dialog>

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
        <el-button type="primary" :loading="uploading" @click="submitUpload" :disabled="fileList.length === 0">
          上传 {{ fileList.length }} 张
        </el-button>
      </template>
    </el-dialog>

    <!-- Image Detail / Annotation Dialog -->
    <el-dialog
      v-model="showImageDialog"
      :title="selectedImage?.filename"
      width="1100px"
      destroy-on-close
    >
      <div class="image-detail" v-if="selectedImage">
        <!-- Left: Canvas for annotation -->
        <div class="detail-image-panel">
          <div class="canvas-toolbar">
            <el-checkbox v-model="annotationMode" label="标注模式" />
            <el-select v-model="selectedClassId" size="small" style="width: 120px" :disabled="!annotationMode">
              <el-option
                v-for="(c, i) in availableClasses"
                :key="i"
                :label="c"
                :value="i"
              />
            </el-select>
            <span class="tool-hint" v-if="annotationMode">在图片上拖拽绘制矩形框</span>
          </div>
          <div
            class="canvas-container"
            ref="canvasContainer"
            @mousedown="onCanvasMouseDown"
            @mousemove="onCanvasMouseMove"
            @mouseup="onCanvasMouseUp"
            @mouseleave="onCanvasMouseUp"
          >
            <img
              ref="detailImgRef"
              :src="selectedImage.url"
              class="detail-img"
              @load="onImageLoad"
              crossorigin="anonymous"
              draggable="false"
            />
            <canvas ref="bboxCanvas" class="bbox-canvas"></canvas>
            <!-- Drawing rect preview -->
            <div
              v-if="isDrawing && drawRect"
              class="draw-rect"
              :style="{
                left: Math.min(drawRect.startX, drawRect.endX) + 'px',
                top: Math.min(drawRect.startY, drawRect.endY) + 'px',
                width: Math.abs(drawRect.endX - drawRect.startX) + 'px',
                height: Math.abs(drawRect.endY - drawRect.startY) + 'px'
              }"
            ></div>
          </div>
        </div>

        <!-- Right: Info panel -->
        <div class="detail-info-panel">
          <h4>检测结果 ({{ localBoxes.length }})</h4>
          <div class="bbox-list" v-if="localBoxes.length">
            <div
              v-for="(box, i) in localBoxes"
              :key="i"
              class="bbox-item"
              :class="{ highlighted: highlightedBbox === i, selected: selectedBbox === i }"
              @mouseenter="highlightBbox(i)"
              @mouseleave="unhighlightBbox"
              @click="selectBbox(i)"
            >
              <div class="bbox-color" :style="{ background: getBboxColor(i) }"></div>
              <div class="bbox-info">
                <span class="bbox-class">{{ box.class_name || ('class_' + box.class_id) }}</span>
                <span class="bbox-coords">
                  {{ (box.bbox[0]*100).toFixed(1) }}%, {{ (box.bbox[1]*100).toFixed(1) }}%, {{ (box.bbox[2]*100).toFixed(1) }}%, {{ (box.bbox[3]*100).toFixed(1) }}%
                </span>
              </div>
              <el-button
                size="small"
                type="danger"
                text
                @click.stop="deleteBbox(i)"
                class="delete-bbox-btn"
              >
                ✕
              </el-button>
            </div>
          </div>
          <div v-else class="no-bbox">无检测结果</div>

          <h4 style="margin-top: 16px">YOLO 格式</h4>
          <div class="yolo-code">
            <pre>{{ getYoloFormat(localBoxes) }}</pre>
          </div>

          <div class="action-buttons" v-if="annotationMode">
            <el-button type="primary" size="small" @click="saveAnnotations" :loading="savingAnnotations">
              保存标注
            </el-button>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import EmptyState from '../components/common/EmptyState.vue'
import {
  getDatasets,
  getDatasetImages,
  getDemoDataset,
  createDataset,
  deleteDataset,
  uploadImages,
  deleteImage,
  saveImageAnnotations,
  autoLabelDinoSam,
  getAutoLabelInfo,
} from '../api/datasets'

const COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']

// State
const activeTab = ref('browse')
const datasets = ref([])
const currentDatasetId = ref(null)
const images = ref([])
const selectedImage = ref(null)
const loadingDatasets = ref(false)
const loadingImages = ref(false)
const showUploadDialog = ref(false)
const showImageDialog = ref(false)
const showCreateDialog = ref(false)
const newDatasetName = ref('')
const creatingDataset = ref(false)
const fileList = ref([])
const uploading = ref(false)

// Dataset cards
const availableClasses = ref(['person', 'bicycle', 'car', 'motorcycle', 'airplane'])

// Image detail / annotation state
const detailImgRef = ref(null)
const bboxCanvas = ref(null)
const canvasContainer = ref(null)
const highlightedBbox = ref(-1)
const selectedBbox = ref(-1)
const localBoxes = ref([])
const annotationMode = ref(false)
const selectedClassId = ref(0)
const savingAnnotations = ref(false)

// Drawing state
const isDrawing = ref(false)
const drawRect = ref(null)

// Auto-label
const autoLabelTask = ref('')
const autoLabelClasses = ref('')
const autoLabelDatasetId = ref(null)
const autoLabelRunning = ref(false)
const autoLabelResults = ref([])
const autoLabelProgress = ref(0)
const autoLabelAnnotated = ref(0)
const autoLabelTotal = ref(0)
const autoLabelMode = ref('未知')
const autoLabelInfo = ref(null)

async function loadDatasets() {
  loadingDatasets.value = true
  try {
    const data = await getDatasets()
    datasets.value = data.datasets || []
    if (datasets.value.length && !currentDatasetId.value) {
      currentDatasetId.value = datasets.value[0].id
      autoLabelDatasetId.value = datasets.value[0].id
    }
  } catch (e) {
    console.error('loadDatasets error:', e)
    ElMessage.error('加载数据集失败')
  } finally {
    loadingDatasets.value = false
  }
}

async function loadDemoDataset() {
  try {
    const data = await getDemoDataset()
    if (data.success && data.dataset) {
      const demoDs = data.dataset
      const existingDemo = datasets.value.find(d => d.id === 'demo')
      if (!existingDemo) {
        datasets.value.unshift({
          id: 'demo',
          name: demoDs.name,
          path: demoDs.path,
          total_images: demoDs.total_images,
          train_count: demoDs.train_count,
          val_count: demoDs.val_count,
          class_names: demoDs.class_names || [],
        })
      }
      if (!currentDatasetId.value) {
        currentDatasetId.value = 'demo'
        autoLabelDatasetId.value = 'demo'
      }
      availableClasses.value = demoDs.class_names || ['object']
    }
  } catch (e) {
    console.error('loadDemoDataset error:', e)
  }
}

async function loadImages() {
  if (!currentDatasetId.value) return
  loadingImages.value = true
  selectedImage.value = null
  try {
    const data = await getDatasetImages(currentDatasetId.value)
    const imgs = data.images || []
    images.value = imgs.map((img, idx) => ({
      ...img,
      url: img.url || `/api/datasets/image/${img.id}`,
      num_objects: img.num_objects || img.boxes?.length || 0,
    }))
    // Update dataset info
    const ds = datasets.value.find(d => d.id === currentDatasetId.value)
    if (ds) {
      ds.total_images = images.value.length
    }
  } catch (e) {
    console.error('loadImages error:', e)
    images.value = []
  } finally {
    loadingImages.value = false
  }
}

function selectDataset(id) {
  currentDatasetId.value = id
}

function onDatasetChange(id) {
  autoLabelDatasetId.value = id
  loadImages()
}

async function onDatasetCommand(cmd, ds) {
  if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm(`确定要删除数据集 "${ds.name}" 吗？`, '删除确认', {
        type: 'warning',
      })
      const res = await deleteDataset(ds.id)
      if (res.success) {
        ElMessage.success('删除成功')
        datasets.value = datasets.value.filter(d => d.id !== ds.id)
        if (currentDatasetId.value === ds.id) {
          currentDatasetId.value = datasets.value[0]?.id || null
        }
      } else {
        ElMessage.error(res.message || '删除失败')
      }
    } catch (e) {
      if (e !== 'cancel') {
        ElMessage.error('删除失败')
      }
    }
  }
}

async function onCreateDataset() {
  if (!newDatasetName.value.trim()) {
    ElMessage.warning('请输入数据集名称')
    return
  }
  creatingDataset.value = true
  try {
    const res = await createDataset(newDatasetName.value.trim())
    if (res.success) {
      ElMessage.success(res.message)
      datasets.value.push(res.dataset)
      currentDatasetId.value = res.dataset.id
      autoLabelDatasetId.value = res.dataset.id
      showCreateDialog.value = false
      newDatasetName.value = ''
      await loadImages()
    } else {
      ElMessage.error(res.message || '创建失败')
    }
  } catch (e) {
    ElMessage.error('创建失败: ' + e.message)
  } finally {
    creatingDataset.value = false
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
    const res = await uploadImages(currentDatasetId.value || 'demo', files)
    if (res.success) {
      ElMessage.success(`成功上传 ${res.uploaded_count} 张图片`)
      showUploadDialog.value = false
      fileList.value = []
      await loadImages()
    } else {
      ElMessage.error(res.message || '上传失败')
    }
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

async function onDeleteImage() {
  if (!selectedImage.value) return
  try {
    await ElMessageBox.confirm('确定要删除这张图片吗？', '删除确认', { type: 'warning' })
    const res = await deleteImage(selectedImage.value.id)
    if (res.success) {
      ElMessage.success('删除成功')
      images.value = images.value.filter(img => img.id !== selectedImage.value.id)
      selectedImage.value = null
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

function openImage(img) {
  selectedImage.value = img
  highlightedBbox.value = -1
  selectedBbox.value = -1
  // Load boxes from image
  localBoxes.value = img.boxes ? img.boxes.map(b => ({...b})) : []
  showImageDialog.value = true
  nextTick(() => {
    initCanvas()
    drawBboxes()
  })
}

function initCanvas() {
  const canvas = bboxCanvas.value
  const img = detailImgRef.value
  const container = canvasContainer.value
  if (!canvas || !img || !container) return

  // Wait for image to load and get its display size
  const updateCanvas = () => {
    const rect = img.getBoundingClientRect()
    const containerRect = container.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = rect.height
    canvas.style.width = rect.width + 'px'
    canvas.style.height = rect.height + 'px'
    canvas.style.left = (img.offsetLeft) + 'px'
    canvas.style.top = (img.offsetTop) + 'px'
  }

  if (img.complete) {
    updateCanvas()
  } else {
    img.onload = updateCanvas
  }
}

function onImageLoad() {
  nextTick(() => {
    initCanvas()
    drawBboxes()
  })
}

function drawBboxes() {
  const canvas = bboxCanvas.value
  const img = detailImgRef.value
  if (!canvas || !img) return

  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  localBoxes.value.forEach((box, i) => {
    const color = getBboxColor(i)
    const hl = i === highlightedBbox.value
    const sel = i === selectedBbox.value

    // YOLO format: [cx, cy, w, h] normalized - convert to pixel
    let x, y, w, h
    if (box.bbox && box.bbox.length === 4) {
      x = (box.bbox[0] - box.bbox[2] / 2) * canvas.width
      y = (box.bbox[1] - box.bbox[3] / 2) * canvas.height
      w = box.bbox[2] * canvas.width
      h = box.bbox[3] * canvas.height
    } else {
      // Fallback: assume absolute pixel values
      x = (box.bbox?.[0] || 0)
      y = (box.bbox?.[1] || 0)
      w = (box.bbox?.[2] || 0)
      h = (box.bbox?.[3] || 0)
    }

    ctx.strokeStyle = color
    ctx.lineWidth = sel ? 3 : (hl ? 3 : 2)
    ctx.globalAlpha = hl || sel ? 1 : 0.7
    ctx.strokeRect(x, y, w, h)

    // Label background
    const label = box.class_name || `class_${box.class_id}`
    ctx.globalAlpha = 0.9
    ctx.fillStyle = color
    const textWidth = ctx.measureText(label).width + 8
    ctx.fillRect(x, y - 18 > 0 ? y - 18 : 0, textWidth, 18)

    ctx.globalAlpha = 1
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 12px sans-serif'
    ctx.fillText(label, x + 4, y - 5 > 0 ? y - 5 : 12)
  })
  ctx.globalAlpha = 1
}

function getBboxColor(i) {
  return COLORS[i % COLORS.length]
}

function highlightBbox(i) {
  highlightedBbox.value = i
  drawBboxes()
}

function unhighlightBbox() {
  highlightedBbox.value = -1
  drawBboxes()
}

function selectBbox(i) {
  selectedBbox.value = i
  drawBboxes()
}

function deleteBbox(i) {
  localBoxes.value.splice(i, 1)
  selectedBbox.value = -1
  drawBboxes()
}

// Canvas mouse handlers for drawing
function getCanvasCoords(e) {
  const canvas = bboxCanvas.value
  const img = detailImgRef.value
  if (!canvas || !img) return { x: 0, y: 0 }

  const rect = img.getBoundingClientRect()
  const containerRect = canvasContainer.value.getBoundingClientRect()

  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height

  return {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top) * scaleY,
    rect,
  }
}

function onCanvasMouseDown(e) {
  if (!annotationMode.value) return
  const coords = getCanvasCoords(e)
  isDrawing.value = true
  drawRect.value = {
    startX: coords.x,
    startY: coords.y,
    endX: coords.x,
    endY: coords.y,
  }
}

function onCanvasMouseMove(e) {
  if (!isDrawing.value || !annotationMode.value) return
  const coords = getCanvasCoords(e)
  drawRect.value.endX = coords.x
  drawRect.value.endY = coords.y
}

function onCanvasMouseUp(e) {
  if (!isDrawing.value || !annotationMode.value) return
  isDrawing.value = false

  if (!drawRect.value) return

  const canvas = bboxCanvas.value
  if (!canvas) return

  // Calculate normalized YOLO bbox [cx, cy, w, h]
  const x1 = Math.min(drawRect.value.startX, drawRect.value.endX)
  const y1 = Math.min(drawRect.value.startY, drawRect.value.endY)
  const x2 = Math.max(drawRect.value.startX, drawRect.value.endX)
  const y2 = Math.max(drawRect.value.startY, drawRect.value.endY)

  const w = x2 - x1
  const h = y2 - y1

  // Minimum size check
  if (w < 5 || h < 5) {
    drawRect.value = null
    return
  }

  // Normalize to YOLO format
  const cx = (x1 + x2) / 2 / canvas.width
  const cy = (y1 + y2) / 2 / canvas.height
  const nw = w / canvas.width
  const nh = h / canvas.height

  // Clamp values
  const clampedCx = Math.max(0, Math.min(1, cx))
  const clampedCy = Math.max(0, Math.min(1, cy))
  const clampedNw = Math.max(0, Math.min(1, nw))
  const clampedNh = Math.max(0, Math.min(1, nh))

  const className = availableClasses.value[selectedClassId.value] || `class_${selectedClassId.value}`

  localBoxes.value.push({
    class_id: selectedClassId.value,
    class_name: className,
    bbox: [clampedCx, clampedCy, clampedNw, clampedNh],
    confidence: 1.0,
  })

  drawRect.value = null
  nextTick(() => drawBboxes())
}

function getYoloFormat(boxes) {
  if (!boxes || boxes.length === 0) return '# 无标注'
  return boxes.map(b =>
    `${b.class_id} ${b.bbox.map(v => v.toFixed(6)).join(' ')}`
  ).join('\n')
}

async function saveAnnotations() {
  if (!selectedImage.value) return
  savingAnnotations.value = true
  try {
    const boxes = localBoxes.value.map(b => ({
      class_id: b.class_id,
      bbox: b.bbox,
    }))
    const res = await saveImageAnnotations(selectedImage.value.id, boxes)
    if (res.success) {
      ElMessage.success(res.message)
      // Update local image data
      selectedImage.value.boxes = [...localBoxes.value]
      selectedImage.value.num_objects = localBoxes.value.length
      // Refresh image list
      await loadImages()
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    savingAnnotations.value = false
  }
}

// Auto-label functions
async function loadAutoLabelInfo() {
  try {
    const data = await getAutoLabelInfo()
    if (data.success) {
      autoLabelInfo.value = data.info
      autoLabelMode.value = data.info.mode || '未知'
    }
  } catch (e) {
    console.error('loadAutoLabelInfo error:', e)
  }
}

async function runAutoLabel() {
  if (!autoLabelClasses.value || !autoLabelTask.value) {
    ElMessage.warning('请填写任务描述和类别')
    return
  }
  autoLabelRunning.value = true
  autoLabelProgress.value = 0
  autoLabelAnnotated.value = 0
  autoLabelTotal.value = 0
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
      autoLabelMode.value = data.mode || 'DINO+SAM'
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
      autoLabelProgress.value = 100
      autoLabelAnnotated.value = data.annotated || 0
      autoLabelTotal.value = data.total || 0

      // Update classes list
      availableClasses.value = classList

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
  if (!selectedImage.value && images.value.length > 0) {
    // Apply to first image as preview
    selectedImage.value = images.value[0]
  }

  if (!selectedImage.value) {
    ElMessage.warning('请先选择一张图片')
    return
  }

  // Show results in the selected image
  if (autoLabelResults.value.length > 0) {
    // Find boxes for this image
    const imgResults = autoLabelResults.value.filter((_, i) => i < 5) // Just show first 5 for demo
    localBoxes.value = imgResults.map(r => ({
      class_id: r.class_id,
      class_name: r.class_name,
      bbox: r.bbox,
      confidence: r.confidence,
    }))

    showImageDialog.value = true
    annotationMode.value = false
    await nextTick()
    drawBboxes()

    ElMessage.info('已预览结果，请点击"保存标注"应用到数据集')
  }

  autoLabelResults.value = []
}

function onImgError(e) {
  e.target.style.display = 'none'
}

// Watch for window resize to redraw
watch(showImageDialog, (val) => {
  if (val) {
    nextTick(() => window.addEventListener('resize', onResize))
  } else {
    window.removeEventListener('resize', onResize)
    isDrawing.value = false
    drawRect.value = null
  }
})

function onResize() {
  initCanvas()
  drawBboxes()
}

watch(currentDatasetId, () => {
  loadImages()
})

onMounted(async () => {
  await loadDatasets()
  // Ensure we have demo dataset
  if (datasets.value.length === 0) {
    await loadDemoDataset()
  }
  await loadImages()
  await loadAutoLabelInfo()
})
</script>

<style scoped>
.datasets-view {
  max-width: 1400px;
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

.header-actions {
  display: flex;
  gap: var(--space-2);
}

/* Dataset Cards */
.dataset-cards {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}

.dataset-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  width: 220px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dataset-card:hover {
  border-color: var(--color-primary-light);
  box-shadow: var(--shadow-sm);
}

.dataset-card.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.card-icon {
  font-size: 20px;
}

.card-name {
  flex: 1;
  font-weight: var(--font-medium);
  font-size: var(--text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-stats {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-num {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.card-classes {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.class-tag {
  font-size: 10px;
  padding: 2px 6px;
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
}

.class-more {
  font-size: 10px;
  color: var(--color-text-muted);
}

/* Tabs */
.main-tabs {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  box-shadow: var(--shadow-sm);
}

/* Browse */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.img-count {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.toolbar-right {
  display: flex;
  gap: var(--space-2);
}

/* Image Grid */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: var(--space-3);
}

.image-card {
  cursor: pointer;
  border-radius: var(--radius-sm);
  overflow: hidden;
  border: 2px solid transparent;
  transition: all var(--transition-fast);
}

.image-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.image-card.selected {
  border-color: var(--color-primary);
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

.selected-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  background: var(--color-primary);
  color: white;
  font-size: 10px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
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

.empty-datasets {
  padding: var(--space-8);
}

/* Auto-label */
.info-alert {
  margin-bottom: var(--space-4);
}

.info-alert p {
  margin-bottom: var(--space-1);
  font-size: var(--text-sm);
}

.service-status {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
}

.status-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online {
  background: var(--color-success);
}

.status-dot.offline {
  background: var(--color-danger);
}

.autolabel-form {
  max-width: 480px;
}

.progress-section {
  margin-bottom: var(--space-4);
}

.progress-bar {
  height: 8px;
  background: var(--color-border);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-bottom: var(--space-2);
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  text-align: center;
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
  gap: var(--space-4);
  height: 65vh;
}

.detail-image-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #1a1a1a;
  border-radius: var(--radius-md);
  overflow: hidden;
}

.canvas-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: #222;
  border-bottom: 1px solid #333;
}

.tool-hint {
  font-size: var(--text-xs);
  color: #888;
}

.canvas-container {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
}

.detail-img {
  max-width: 100%;
  max-height: 100%;
  display: block;
  user-select: none;
}

.bbox-canvas {
  position: absolute;
  pointer-events: none;
}

.draw-rect {
  position: absolute;
  border: 2px dashed #fff;
  background: rgba(255, 255, 255, 0.1);
  pointer-events: none;
}

.detail-info-panel {
  width: 280px;
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
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
  border: 1px solid transparent;
}

.bbox-item:hover {
  background: var(--color-primary-bg);
}

.bbox-item.highlighted {
  border-color: var(--color-primary-light);
}

.bbox-item.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}

.bbox-color {
  width: 4px;
  height: 24px;
  border-radius: 2px;
  flex-shrink: 0;
}

.bbox-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.bbox-class {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bbox-coords {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.delete-bbox-btn {
  padding: 2px 6px;
  min-height: auto;
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

.action-buttons {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}
</style>
