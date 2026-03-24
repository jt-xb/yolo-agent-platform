<template>
  <div class="datasets-view">

    <!-- ========== 页面标题区 ========== -->
    <div class="page-header">
      <div class="page-title-area">
        <h2>📁 数据集管理</h2>
        <p class="page-subtitle">上传图片、自动标注、手动修正，全程管理您的训练数据</p>
      </div>
      <div class="header-actions">
        <el-select v-model="currentDatasetId" placeholder="选择数据集" size="default" style="width: 200px" @change="onDatasetChange" :loading="loadingDatasetList">
          <el-option v-for="ds in datasetList" :key="ds.id" :label="ds.name" :value="ds.id">
            <span>{{ ds.name }}</span>
            <span style="float:right; color:#aaa; font-size:11px">{{ ds.total_images }}张</span>
          </el-option>
        </el-select>
        <el-button @click="showUploadDialog = true">+ 上传图片</el-button>
      </div>
    </div>

    <!-- ========== 功能切换tabs ========== -->
    <div class="tabs-bar">
      <el-button
        v-for="tab in tabs"
        :key="tab.key"
        :type="activeTab === tab.key ? 'primary' : ''"
        :class="{ 'tab-btn-active': activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        {{ tab.label }}
        <el-badge v-if="tab.key === 'browse' && datasetInfo?.total_images" :value="datasetInfo.total_images" class="tab-badge" />
      </el-button>
    </div>

    <!-- ========== 模式1: 浏览图片 ========== -->
    <div v-if="activeTab === 'browse'" class="browse-panel">
      <!-- 数据集统计卡片 -->
      <div class="dataset-stats" v-if="datasetInfo">
        <div class="stat-card">
          <div class="stat-icon">📷</div>
          <div class="stat-content">
            <div class="stat-value">{{ datasetInfo.total_images || 0 }}</div>
            <div class="stat-label">总图片数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">🏋️</div>
          <div class="stat-content">
            <div class="stat-value">{{ datasetInfo.train_count || 0 }}</div>
            <div class="stat-label">训练集</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">✅</div>
          <div class="stat-content">
            <div class="stat-value">{{ datasetInfo.val_count || 0 }}</div>
            <div class="stat-label">验证集</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">🎯</div>
          <div class="stat-content">
            <div class="stat-value">{{ totalObjects }}</div>
            <div class="stat-label">已标注目标</div>
          </div>
        </div>
        <div class="stat-card classes-card" v-if="datasetInfo.class_names?.length">
          <div class="class-tags">
            <span class="classes-label">类别：</span>
            <el-tag v-for="(cls, i) in datasetInfo.class_names" :key="i" size="small">{{ cls }}</el-tag>
          </div>
        </div>
      </div>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <div class="filter-left">
          <span class="filter-label">筛选：</span>
          <el-radio-group v-model="filterSplit" size="small">
            <el-radio-button label="all">全部 ({{ filteredImages.length }})</el-radio-button>
            <el-radio-button label="train">训练集</el-radio-button>
            <el-radio-button label="val">验证集</el-radio-button>
          </el-radio-group>
        </div>
        <el-input v-model="searchText" placeholder="搜索图片..." size="small" style="width: 200px" clearable>
          <template #prefix>🔍</template>
        </el-input>
      </div>

      <!-- 加载状态 -->
      <div v-if="loadingImages" class="loading-state">
        <el-icon class="is-loading" size="32"><loading /></el-icon>
        <p>正在加载图片...</p>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="loadError" class="error-state">
        <span class="error-icon">❌</span>
        <p>{{ loadError }}</p>
        <el-button size="small" @click="loadDataset">重试</el-button>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!datasetInfo || filteredImages.length === 0" class="empty-state">
        <span class="empty-icon">📂</span>
        <p>暂无图片</p>
        <p class="empty-hint">上传图片或从其他数据集导入</p>
        <el-button type="primary" size="small" @click="showUploadDialog = true">上传图片</el-button>
      </div>

      <!-- 图片网格 -->
      <div v-else class="image-grid">
        <div v-for="img in filteredImages" :key="img.id" class="image-card" @click="selectImage(img)">
          <div class="image-wrapper">
            <img :src="img.url" :alt="img.filename" @error="onImgError" />
            <div class="image-overlay">
              <span class="obj-count">{{ img.num_objects || 0 }} 个目标</span>
            </div>
            <div class="split-badge" :class="img.split">{{ img.split }}</div>
            <div v-if="img.num_objects > 0" class="annotated-badge">已标注</div>
          </div>
          <div class="image-info">
            <span class="filename" :title="img.filename">{{ img.filename }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ========== 模式2: 自动标注流程 ========== -->
    <div v-if="activeTab === 'autolabel'" class="autolabel-panel">
      <el-alert title="自动标注工作原理" type="info" :closable="false" style="margin: 20px 0">
        <template #default>
          <div style="font-size: 13px; line-height: 1.8">
            <b>Step 1 - 文本引导定位（Grounding DINO）</b>：输入文本描述（如"person without helmet"），模型在图像中定位所有匹配目标，输出候选区域和置信度<br>
            <b>Step 2 - 精确掩码生成（SAM）</b>：对每个候选区域，SAM 生成精确的分割掩码，从掩码计算最小外接矩形<br>
            <b>Step 3 - 后处理过滤</b>：过滤低置信度框，合并重叠框，按类别分组<br>
            <b>Step 4 - 格式转换</b>：将结果转换为 YOLO 格式（class_id + 归一化坐标），保存为 .txt 文件
          </div>
        </template>
      </el-alert>

      <el-card shadow="hover" style="margin: 20px 0">
        <h4 style="margin: 0 0 15px 0">🎯 输入检测任务</h4>
        <div style="margin-bottom: 15px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap">
          <span style="color: #666; font-size: 14px">目标数据集：</span>
          <el-select v-model="autoLabelDatasetId" placeholder="选择数据集" size="default" style="width: 200px">
            <el-option v-for="ds in datasetList" :key="ds.id" :label="ds.name" :value="ds.id">
              <span>{{ ds.name }}</span>
              <span style="float:right; color:#aaa; font-size:11px">{{ ds.total_images }}张</span>
            </el-option>
          </el-select>
          <span style="color: #aaa; font-size: 12px" v-if="autoLabelDatasetId">共 {{ getDatasetImageCount(autoLabelDatasetId) }} 张图片可用</span>
        </div>
        <el-input v-model="autoLabelTask" type="textarea" :rows="2" placeholder="例如：检测图片中未佩戴安全帽的人员" style="margin-bottom: 15px" />
        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 15px">
          <span style="color: #666; line-height: 32px">检测类别：</span>
          <el-tag v-for="(cls, i) in autoLabelClasses" :key="i" closable @close="removeClass(i)" style="margin-right: 8px">{{ cls }}</el-tag>
          <el-input v-model="newClassName" placeholder="+ 添加类别" size="small" style="width: 120px" @keydown.enter="addClass">
            <template #append><el-button @click="addClass" size="small">+</el-button></template>
          </el-input>
        </div>
        <el-button type="primary" @click="runAutoLabel" :loading="autoLabelRunning" :disabled="!autoLabelTask || autoLabelClasses.length === 0">
          🚀 开始自动标注
        </el-button>
      </el-card>

      <div v-if="autoLabelRunning || autoLabelSteps.length > 0" class="pipeline-container">
        <h4>⚙️ 标注流水线实时状态</h4>
        <div class="pipeline-steps">
          <div v-for="(step, i) in autoLabelSteps" :key="i" class="pipeline-step" :class="step.status">
            <div class="step-indicator">
              <el-icon v-if="step.status === 'running'" class="is-loading"><loading /></el-icon>
              <span v-else-if="step.status === 'done'">✅</span>
              <span v-else-if="step.status === 'error'">❌</span>
              <span v-else>⏳</span>
            </div>
            <div class="step-content">
              <div class="step-title">{{ step.title }}</div>
              <div class="step-desc">{{ step.description }}</div>
              <div v-if="step.status === 'running'" class="step-progress">
                <el-progress :percentage="step.progress || 0" :stroke-width="6" />
              </div>
            </div>
          </div>
        </div>

        <div v-if="autoLabelResults.length > 0" class="results-section">
          <h4>🎯 检测结果预览（{{ autoLabelResults.length }} 个对象）</h4>
          <div class="result-preview-grid">
            <div v-for="(r, i) in autoLabelResults" :key="i" class="result-card" :style="{ '--result-color': getBboxColor(r.class_id) }">
              <div class="result-color-bar"></div>
              <div class="result-info">
                <span class="result-class">{{ r.class_name }}</span>
                <span class="result-conf">置信度: {{ (r.confidence * 100).toFixed(1) }}%</span>
                <span class="result-bbox">bbox: {{ r.bbox.map(v => v.toFixed(3)).join(', ') }}</span>
              </div>
            </div>
          </div>
          <div style="margin-top: 15px">
            <el-button type="success" @click="applyAutoLabelResults">✅ 应用标注结果到数据集</el-button>
            <el-button @click="clearAutoLabel">清空</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- ========== 模式4: 数据集管理 ========== -->
    <div v-if="activeTab === 'datasets'" class="datasets-mgmt">
      <el-row :gutter="20" style="margin: 20px 0">
        <el-col :span="8">
          <el-button type="primary" @click="showImportDialog = true">📥 导入新数据集</el-button>
          <el-button @click="loadDatasetList">🔄 刷新列表</el-button>
        </el-col>
      </el-row>

      <el-table :data="datasetList" stripe size="medium" v-loading="loading">
        <el-table-column prop="name" label="数据集名称" min-width="160" />
        <el-table-column prop="id" label="数据集ID" width="160">
          <template #default="{ row }">
            <code style="font-size: 11px">{{ row.id }}</code>
          </template>
        </el-table-column>
        <el-table-column label="图片数" width="100">
          <template #default="{ row }">{{ row.total_images }}</template>
        </el-table-column>
        <el-table-column label="训练/验证/测试" width="160">
          <template #default="{ row }">
            {{ row.train_count }} / {{ row.val_count }} / {{ row.test_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="类别" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="(c,i) in row.class_names" :key="i" size="small" style="margin-right:4px">{{ c }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="switchToDataset(row.id)">切换</el-button>
            <el-button size="small" type="danger" @click="confirmMerge(row)" :disabled="datasetList.length < 2">合并</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 导入对话框 -->
      <el-dialog v-model="showImportDialog" title="📥 导入数据集" width="500px">
        <el-form label-width="100px">
          <el-form-item label="上传图片">
            <el-upload ref="importUploadRef" :auto-upload="false" :multiple="true" accept="image/*,.zip" :file-list="importFileList" :on-change="onImportFileChange" :on-remove="onImportFileRemove" drag style="width:100%">
              <el-icon><upload-filled /></el-icon>
              <div>拖拽图片或 ZIP 压缩包到这里<br><small style="color:#aaa">支持 .jpg/.png/.zip（ZIP内含图片）</small></div>
            </el-upload>
          </el-form-item>
          <el-form-item label="训练集比例">
            <el-slider v-model="importTrainRatio" :min="0.1" :max="1.0" :step="0.05" show-stops :max-value="1.0" />
            <div style="font-size:12px;color:#888">训练 {{ Math.round(importTrainRatio*100) }}% / 验证 {{ Math.round(importValRatio*100) }}% / 测试 {{ Math.round((1-importTrainRatio-importValRatio)*100) }}%</div>
          </el-form-item>
          <el-form-item label="验证集比例">
            <el-slider v-model="importValRatio" :min="0" :max="0.9" :step="0.05" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showImportDialog = false">取消</el-button>
          <el-button type="primary" @click="doImportDataset" :loading="importing">导入</el-button>
        </template>
      </el-dialog>

      <!-- 合并对话框 -->
      <el-dialog v-model="showMergeDialog" title="🔀 合并数据集" width="450px">
        <p style="margin-bottom:15px">
          将 <b>{{ mergeSource1?.name }}</b> + <b>{{ mergeSource2?.name }}</b> 合并为：
        </p>
        <el-form-item label="新数据集名称">
          <el-input v-model="mergeTargetName" placeholder="输入名称" />
        </el-form-item>
        <template #footer>
          <el-button @click="showMergeDialog = false">取消</el-button>
          <el-button type="primary" @click="doMergeDataset" :loading="merging">合并</el-button>
        </template>
      </el-dialog>
    </div>

    <!-- ========== 模式3: 手动标注 ========== -->
    <div v-if="activeTab === 'annotate'" class="annotate-panel">
      <div v-if="!annotatingImage" style="margin: 20px 0">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px">
          <h3 style="margin: 0">选择要标注的图片</h3>
          <div style="font-size: 13px; color: #888">💡 按住鼠标拖动即可画框，点击已有框可编辑或删除</div>
        </div>
        <div class="image-grid">
          <div v-for="img in allImagesForAnnotate" :key="img.id" class="image-card" @click="startAnnotate(img)">
            <div class="image-wrapper">
              <img :src="img.url" :alt="img.filename" @error="onImgError" />
              <div class="image-overlay"><span class="obj-count">{{ img.num_objects }} 个目标</span></div>
            </div>
            <div class="image-info"><span class="filename">{{ img.filename }}</span></div>
          </div>
        </div>
      </div>

      <div v-if="annotatingImage" class="annotate-workspace">
        <!-- 工具栏 -->
        <div class="annotate-toolbar">
          <el-button @click="cancelAnnotate" size="small">← 返回列表</el-button>
          <el-divider direction="vertical" />
          <span style="color: #666; font-size: 13px">{{ annotatingImage.filename }}</span>
          <span style="margin-left: 12px; font-size: 12px; color: #aaa">| 按住拖动画框 | 点击框选类别 | Del键删除选中框 |</span>
          <div style="margin-left: auto">
            <el-button type="success" size="small" @click="saveAnnotations" :loading="savingAnnotations">💾 保存 {{ annotationBoxes.length }} 个标注</el-button>
          </div>
        </div>

        <!-- 画布区域 -->
        <div class="annotate-content">
          <div class="canvas-wrap" ref="annCanvasWrap">
            <img
              :src="annotatingImage.url"
              alt=""
              ref="annImgRef"
              @load="onAnnImgLoad"
              @error="onImgError"
              class="ann-img"
              crossorigin="anonymous"
              draggable="false"
            />
            <canvas
              ref="annCanvas"
              class="ann-canvas"
              @mousedown="onCvMousedown"
              @mousemove="onCvMousemove"
              @mouseup="onCvMouseup"
              @mouseleave="onCvMouseleave"
            />
          </div>

          <!-- 侧边栏 -->
          <div class="ann-sidebar">
            <!-- 类别选择 -->
            <div class="ann-section">
              <div class="ann-section-title">🎨 框的颜色 / 类别</div>
              <div
                v-for="(cls, i) in availableClasses"
                :key="i"
                class="ann-class-btn"
                :class="{ active: currentClassId === i }"
                :style="{ '--c': getBboxColor(i) }"
                @click="currentClassId = i"
              >
                <span class="ann-cls-dot" :style="{ background: getBboxColor(i) }"></span>
                {{ cls }}
              </div>
              <div v-if="selectedBoxIndex >= 0" style="margin-top: 10px; padding: 8px; background: #fff3e0; border-radius: 6px; font-size: 12px">
                ✅ 已选中第 {{ selectedBoxIndex + 1 }} 个框
                <br>当前类别：
                <b :style="{ color: getBboxColor(annotationBoxes[selectedBoxIndex]?.class_id) }">
                  {{ annotationBoxes[selectedBoxIndex]?.class_name }}
                </b>
              </div>
            </div>

            <!-- 框列表 -->
            <div class="ann-section" style="margin-top: 12px">
              <div class="ann-section-title">📋 已有标注 ({{ annotationBoxes.length }})</div>
              <div class="ann-box-list">
                <div
                  v-for="(box, i) in annotationBoxes"
                  :key="i"
                  class="ann-box-item"
                  :class="{ selected: selectedBoxIndex === i }"
                  :style="{ '--c': getBboxColor(box.class_id) }"
                  @click="selectBox(i)"
                >
                  <span class="ann-box-num">{{ i + 1 }}</span>
                  <span class="ann-box-name">{{ box.class_name }}</span>
                  <span class="ann-box-del" @click.stop="deleteBox(i)">✕</span>
                </div>
                <div v-if="annotationBoxes.length === 0" style="color: #bbb; text-align: center; padding: 16px; font-size: 13px">
                  还没有标注<br>在图片上拖动画框
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ========== 图片详情弹窗 ========== -->
    <el-dialog v-model="showImageDialog" title="图片详情 + 标注结果" width="900px" fullscreen>
      <div v-if="selectedImage" class="image-detail">
        <div class="detail-image-panel">
          <div class="canvas-wrapper" ref="canvasWrapper">
            <img :src="selectedImage.url" :alt="selectedImage.filename" @load="onImageLoad" @error="onImgError" ref="detailImgRef" class="detail-img" crossorigin="anonymous" />
            <canvas ref="bboxCanvas" class="bbox-canvas"></canvas>
          </div>
        </div>
        <div class="detail-info-panel">
          <h4>📋 标注信息</h4>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="文件名">{{ selectedImage.filename }}</el-descriptions-item>
            <el-descriptions-item label="数据集划分"><el-tag size="small" :type="selectedImage.split === 'train' ? 'success' : 'warning'">{{ selectedImage.split }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="目标数量">{{ selectedImage.num_objects }}</el-descriptions-item>
          </el-descriptions>
          <h4 style="margin-top: 20px">🎯 标注框列表</h4>
          <div class="bbox-list">
            <div v-for="(box, i) in selectedImage.boxes" :key="i" class="bbox-item" :style="{ '--bbox-color': getBboxColor(box.class_id) }"
              @mouseenter="highlightBbox(i)" @mouseleave="unhighlightBbox">
              <div class="bbox-color-bar"></div>
              <div class="bbox-info">
                <span class="bbox-class">{{ box.class_name }}</span>
                <span class="bbox-id">#{{ box.class_id }}</span>
              </div>
              <div class="bbox-coords">{{ box.bbox.map(v => v.toFixed(3)).join(', ') }}</div>
            </div>
          </div>
          <h4 style="margin-top: 20px">📄 YOLO 格式</h4>
          <pre class="yolo-format">{{ getYoloFormat(selectedImage) }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="prevImage" :disabled="currentImageIndex <= 0">← 上一张</el-button>
        <span style="color: #999; font-size: 13px; margin: 0 8px">{{ currentImageIndex + 1 }} / {{ allCurrentImages.length }}</span>
        <el-button @click="nextImage" :disabled="currentImageIndex >= allCurrentImages.length - 1">下一张 →</el-button>
        <el-divider direction="vertical" />
        <el-button @click="showImageDialog = false">关闭</el-button>
        <el-button type="danger" @click="deleteImage(selectedImage)">删除图片</el-button>
      </template>
    </el-dialog>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传图片" width="500px">
      <el-upload ref="uploadRef" :auto-upload="false" :multiple="true" accept="image/*" :file-list="fileList"
        :on-change="onFileChange" :on-remove="onFileRemove" drag style="width: 100%">
        <el-icon><upload-filled /></el-icon>
        <div>拖拽图片到此处，或点击选择</div>
        <template #tip><div class="el-upload__tip">支持 jpg、png、bmp 格式</div></template>
      </el-upload>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="submitUpload" :loading="uploading">上传 {{ fileList.length }} 张</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Loading } from '@element-plus/icons-vue'

const API = '/api'
const COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']

export default {
  name: 'DatasetsView',
  components: { UploadFilled, Loading },
  setup() {
    const datasetInfo = ref(null)
    const loading = ref(false)
    const loadingImages = ref(false)
    const loadingDatasetList = ref(false)
    const loadError = ref(null)
    const activeTab = ref('browse')
    const filterSplit = ref('all')
    const searchText = ref('')
    const showImageDialog = ref(false)
    const showUploadDialog = ref(false)
    const uploading = ref(false)
    const fileList = ref([])
    const selectedImage = ref(null)
    const canvasWrapper = ref(null)
    const bboxCanvas = ref(null)
    const detailImgRef = ref(null)
    const highlightedBbox = ref(-1)

    // Tabs 定义
    const tabs = [
      { key: 'browse', label: '浏览图片', icon: '🖼️' },
      { key: 'autolabel', label: '自动标注', icon: '🤖' },
      { key: 'annotate', label: '手动标注', icon: '✏️' },
      { key: 'datasets', label: '数据集管理', icon: '📦' },
    ]

    // 自动标注
    const autoLabelTask = ref('检测图片中的人物和车辆')
    const autoLabelClasses = ref(['person', 'car', 'bicycle'])
    const newClassName = ref('')
    const autoLabelRunning = ref(false)
    const autoLabelSteps = ref([])
    const autoLabelResults = ref([])
    const autoLabelDatasetId = ref('')
    const currentImageIndex = ref(0)
    const allCurrentImages = ref([])

    // 手动标注
    const annotatingImage = ref(null)
    const annotationBoxes = ref([])
    const selectedBoxIndex = ref(-1)
    const currentClassId = ref(0)
    const savingAnnotations = ref(false)
    const availableClasses = ref(['person', 'bicycle', 'car', 'motorcycle', 'airplane'])

    // 数据集列表管理
    const datasetList = ref([])
    const currentDatasetId = ref('demo')
    const showImportDialog = ref(false)
    const showMergeDialog = ref(false)
    const importing = ref(false)
    const merging = ref(false)
    const importFileList = ref([])
    const importTrainRatio = ref(0.8)
    const importValRatio = ref(0.1)
    const mergeTargetName = ref('')
    const mergeSource1 = ref(null)
    const mergeSource2 = ref(null)

    // 切换 Tab
    const switchTab = (tab) => {
      activeTab.value = tab
      if (tab === 'browse') {
        loadDataset().catch(() => {})
      }
    }

    // 加载数据集列表
    const loadDatasetList = async () => {
      loadingDatasetList.value = true
      try {
        const res = await fetch(`${API}/datasets/all`)
        if (!res.ok) throw new Error('加载数据集列表失败')
        const data = await res.json()
        datasetList.value = data.datasets || []
      } catch (e) {
        console.error('加载数据集列表失败:', e)
        ElMessage.warning('无法加载数据集列表')
      } finally {
        loadingDatasetList.value = false
      }
    }

    // 加载数据集
    const loadDataset = async () => {
      loadingImages.value = true
      loadError.value = null
      try {
        const dsId = currentDatasetId.value || 'demo'
        const res = await fetch(`${API}/datasets/${dsId}`)
        if (!res.ok) {
          if (res.status === 404) {
            // 尝试加载 demo 数据集
            const demoRes = await fetch(`${API}/datasets/demo`)
            if (demoRes.ok) {
              const demoData = await demoRes.json()
              if (demoData.success) {
                datasetInfo.value = demoData.dataset
                availableClasses.value = demoData.dataset.class_names || []
                currentDatasetId.value = 'demo'
                return
              }
            }
            throw new Error('数据集不存在')
          }
          throw new Error('加载数据集失败')
        }
        const data = await res.json()
        if (data.success) {
          datasetInfo.value = data.dataset
          availableClasses.value = data.dataset.class_names || []
        } else {
          throw new Error(data.message || '加载数据集失败')
        }
      } catch (e) {
        console.error('加载失败:', e)
        loadError.value = e.message || '加载数据集失败'
        datasetInfo.value = null
      } finally {
        loadingImages.value = false
      }
    }

    // 切换数据集
    const onDatasetChange = async (dsId) => {
      currentDatasetId.value = dsId
      autoLabelDatasetId.value = dsId
      filterSplit.value = 'all'
      searchText.value = ''
      await loadDataset()
      activeTab.value = 'browse'
    }

    const switchToDataset = async (dsId) => {
      currentDatasetId.value = dsId
      await onDatasetChange(dsId)
    }

    const onImportFileChange = (file, list) => { importFileList.value = list }
    const onImportFileRemove = (file, list) => { importFileList.value = list }

    const doImportDataset = async () => {
      if (!importFileList.value.length) { ElMessage.warning('请先选择文件'); return }
      importing.value = true
      try {
        const fd = new FormData()
        for (const f of importFileList.value) {
          fd.append('files', f.raw)
        }
        fd.append('train_ratio', importTrainRatio.value.toFixed(2))
        fd.append('val_ratio', importValRatio.value.toFixed(2))
        fd.append('test_ratio', Math.max(0, (1 - importTrainRatio.value - importValRatio.value)).toFixed(2))
        const res = await fetch(`${API}/datasets/import?train_ratio=${importTrainRatio.value}&val_ratio=${importValRatio.value}&test_ratio=${1 - importTrainRatio.value - importValRatio.value}`, { method: 'POST', body: fd })
        const data = await res.json()
        if (data.success) {
          ElMessage.success(data.message)
          showImportDialog.value = false
          importFileList.value = []
          await loadDatasetList()
          await onDatasetChange(data.dataset.id)
        } else {
          ElMessage.error(data.message || '导入失败')
        }
      } catch (e) {
        ElMessage.error('导入失败: ' + e.message)
      } finally {
        importing.value = false
      }
    }

    const confirmMerge = (ds) => {
      if (datasetList.value.length < 2) { ElMessage.warning('至少需要2个数据集才能合并'); return }
      mergeSource1.value = ds
      mergeSource2.value = datasetList.value.find(d => d.id !== ds.id) || null
      mergeTargetName.value = `合并_${mergeSource1.value.name}_${mergeSource2.value?.name}`
      showMergeDialog.value = true
    }

    const doMergeDataset = async () => {
      if (!mergeSource1.value || !mergeSource2.value) { ElMessage.warning('请选择要合并的数据集'); return }
      merging.value = true
      try {
        const res = await fetch(`${API}/datasets/merge?source_id_1=${mergeSource1.value.id}&source_id_2=${mergeSource2.value.id}&target_name=${encodeURIComponent(mergeTargetName.value)}`, { method: 'POST' })
        const data = await res.json()
        if (data.success) {
          ElMessage.success(data.message)
          showMergeDialog.value = false
          await loadDatasetList()
          await onDatasetChange(data.dataset.id)
        } else {
          ElMessage.error(data.message || '合并失败')
        }
      } catch (e) {
        ElMessage.error('合并失败: ' + e.message)
      } finally {
        merging.value = false
      }
    }

    onMounted(() => {
      loadDatasetList()
      loadDataset()
    })

    const filteredImages = computed(() => {
      if (!datasetInfo.value) return []
      let images = datasetInfo.value.images || []
      if (filterSplit.value !== 'all') images = images.filter(img => img.split === filterSplit.value)
      if (searchText.value) {
        const q = searchText.value.toLowerCase()
        images = images.filter(img => img.filename.toLowerCase().includes(q))
      }
      return images
    })

    const allImagesForAnnotate = computed(() => datasetInfo.value?.images || [])
    const totalObjects = computed(() => datasetInfo.value?.images.reduce((sum, img) => sum + img.num_objects, 0) || 0)

    // 自动标注
    const addClass = () => {
      const c = newClassName.value.trim()
      if (c && !autoLabelClasses.value.includes(c)) autoLabelClasses.value.push(c)
      newClassName.value = ''
    }
    const removeClass = (i) => { autoLabelClasses.value.splice(i, 1) }

    const runAutoLabel = async () => {
      if (!autoLabelTask.value || autoLabelClasses.value.length === 0) {
        ElMessage.warning('请输入任务描述和至少一个类别')
        return
      }
      autoLabelRunning.value = true
      autoLabelSteps.value = []
      autoLabelResults.value = []

      const steps = [
        { title: '🔍 Step 1: 文本引导定位（Grounding DINO）', description: '输入文本描述，扫描图像所有候选区域...', status: 'pending' },
        { title: '🎭 Step 2: 精确掩码生成（SAM）', description: '对候选区域生成精细分割掩码...', status: 'pending' },
        { title: '🗑️ Step 3: 后处理过滤', description: '过滤低置信度框，合并重叠区域...', status: 'pending' },
        { title: '💾 Step 4: 格式转换与保存', description: '转换为 YOLO 格式保存...', status: 'pending' },
      ]

      // 显示步骤
      for (const step of steps) {
        autoLabelSteps.value.push({ ...step, progress: 0 })
      }

      try {
        // 调用后端 API 进行真实自动标注
        const res = await fetch(`${API}/datasets/dino-sam-auto-label`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            task_description: autoLabelTask.value,
            class_names: autoLabelClasses.value,
            dataset_id: autoLabelDatasetId.value || 'demo',
            box_threshold: 0.25,
          }),
        })

        const data = await res.json()

        // 将所有步骤标记为完成（后端已完成全部流程）
        for (let i = 0; i < steps.length; i++) {
          autoLabelSteps.value[i] = { ...autoLabelSteps.value[i], status: 'done', progress: 100 }
        }

        if (data.success) {
          ElMessage.success(data.message || '自动标注完成')

          // 转换后端返回的结果为前端格式
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

          // 显示模式信息
          if (data.mode) {
            console.log(`[AutoLabel] 模式: ${data.mode}, DINO: ${data.dino_available}, SAM: ${data.sam_available}, YOLO回退: ${data.yolo_fallback}`)
          }

          // 刷新数据集
          await loadDataset()
        } else {
          ElMessage.error(data.message || '自动标注失败')
          // 如果失败，标记最后一步为错误
          if (autoLabelSteps.value.length > 0) {
            autoLabelSteps.value[autoLabelSteps.value.length - 1] = {
              ...autoLabelSteps.value[autoLabelSteps.value.length - 1],
              status: 'error'
            }
          }
        }
      } catch (e) {
        console.error('[AutoLabel] API调用失败:', e)
        ElMessage.error('调用自动标注服务失败: ' + e.message)
        // 将所有 pending 步骤标记为错误
        for (let i = 0; i < autoLabelSteps.value.length; i++) {
          if (autoLabelSteps.value[i].status === 'pending') {
            autoLabelSteps.value[i] = { ...autoLabelSteps.value[i], status: 'error' }
          }
        }
      } finally {
        autoLabelRunning.value = false
      }
    }

    const applyAutoLabelResults = async () => {
      ElMessage.success(`已将 ${autoLabelResults.value.length} 个标注结果应用到数据集`)
      autoLabelResults.value = []
      autoLabelSteps.value = []
      await loadDataset()
    }

    const clearAutoLabel = () => { autoLabelResults.value = []; autoLabelSteps.value = [] }

    // 手动标注
    const startAnnotate = (img) => {
      annotatingImage.value = JSON.parse(JSON.stringify(img))
      annotationBoxes.value = JSON.parse(JSON.stringify(img.boxes || []))
      selectedBoxIndex.value = -1
      drawState = null
      tempRect = null
      mousePos = null
      document.addEventListener('keydown', onAnnKeydown)
      nextTick(() => onAnnImgLoad())
    }

    const onAnnotateImageLoad = () => {
      nextTick(() => {
        if (!annImgRef.value) return
        imgDisplayWidth.value = annImgRef.value.offsetWidth
        imgDisplayHeight.value = annImgRef.value.offsetHeight
      })
    }

    const bboxToPixel = (bbox) => ({
      x: (bbox[0] - bbox[2] / 2) * imgDisplayWidth.value,
      y: (bbox[1] - bbox[3] / 2) * imgDisplayHeight.value,
      w: bbox[2] * imgDisplayWidth.value,
      h: bbox[3] * imgDisplayHeight.value
    })

    // Canvas 标注相关
    const annCanvas = ref(null)
    const annImgRef = ref(null)
    const annCvRef = ref(null)
    const annCvWrap = ref(null)
    let annCtx = null
    let dw = 0, dh = 0
    let iw = 0, ih = 0
    let drawState = null
    let mousePos = null
    let tempRect = null
    const HANDLE = 8

    const onAnnImgLoad = () => {
      nextTick(() => {
        const canvas = annCanvas.value
        const img = annImgRef.value
        if (!canvas || !img) return
        dw = img.offsetWidth
        dh = img.offsetHeight
        iw = img.naturalWidth
        ih = img.naturalHeight
        canvas.width = dw
        canvas.height = dh
        annCtx = canvas.getContext('2d')
        redrawAnn()
      })
    }

    const redrawAnn = () => {
      if (!annCtx || !dw) return
      const ctx = annCtx
      ctx.clearRect(0, 0, dw, dh)

      annotationBoxes.value.forEach((box, i) => {
        const sel = i === selectedBoxIndex.value
        const color = getBboxColor(box.class_id)
        const [cx, cy, bw, bh] = box.bbox
        const x = (cx - bw / 2) * dw
        const y = (cy - bh / 2) * dh
        const w = bw * dw
        const h = bh * dh

        ctx.globalAlpha = sel ? 0.25 : 0.12
        ctx.fillStyle = color
        ctx.fillRect(x, y, w, h)

        ctx.globalAlpha = 1
        ctx.strokeStyle = color
        ctx.lineWidth = sel ? 3 : 2
        ctx.setLineDash([])
        ctx.strokeRect(x, y, w, h)

        ctx.fillStyle = color
        ctx.globalAlpha = 0.85
        const label = box.class_name
        ctx.font = `bold 13px system-ui, sans-serif`
        const tw = ctx.measureText(label).width
        ctx.fillRect(x, y - 18, tw + 8, 17)

        ctx.globalAlpha = 1
        ctx.fillStyle = 'white'
        ctx.fillText(label, x + 4, y - 5)

        if (sel) {
          ctx.fillStyle = 'white'
          ctx.strokeStyle = color
          ctx.lineWidth = 2
          const handles = [
            [x, y], [x + w/2, y], [x + w, y],
            [x, y + h/2], [x + w, y + h/2],
            [x, y + h], [x + w/2, y + h], [x + w, y + h]
          ]
          handles.forEach(([hx, hy]) => {
            ctx.beginPath()
            ctx.arc(hx, hy, HANDLE, 0, Math.PI * 2)
            ctx.fill()
            ctx.stroke()
          })
        }
      })

      if (tempRect) {
        ctx.strokeStyle = '#409eff'
        ctx.lineWidth = 2
        ctx.setLineDash([5, 4])
        ctx.strokeRect(tempRect.x, tempRect.y, tempRect.w, tempRect.h)
        ctx.setLineDash([])
        ctx.fillStyle = 'rgba(64,158,255,0.1)'
        ctx.fillRect(tempRect.x, tempRect.y, tempRect.w, tempRect.h)
        const label = `${Math.round(tempRect.w)}×${Math.round(tempRect.h)}`
        ctx.font = '12px system-ui, sans-serif'
        const tw = ctx.measureText(label).width
        ctx.fillStyle = 'rgba(0,0,0,0.7)'
        ctx.fillRect(tempRect.x + 3, tempRect.y + tempRect.h + 3, tw + 6, 15)
        ctx.fillStyle = 'white'
        ctx.fillText(label, tempRect.x + 6, tempRect.y + tempRect.h + 15)
      }

      if (annCanvas.value) {
        const mode = getCanvasCursor(mousePos)
        annCanvas.value.style.cursor = mode
      }
    }

    const getCanvasCursor = (pos) => {
      if (!pos || selectedBoxIndex.value < 0) {
        if (drawState && drawState.mode === 'new') return 'crosshair'
        return 'crosshair'
      }
      const [cx, cy, bw, bh] = annotationBoxes.value[selectedBoxIndex.value].bbox
      const bx = (cx - bw / 2) * dw
      const by = (cy - bh / 2) * dh
      const w = bw * dw
      const h = bh * dh
      const hx = pos.x, hy = pos.y
      const corners = [[bx,by],[bx+w,by],[bx,by+h],[bx+w,by+h]]
      for (const [cx2,cy2] of corners) {
        if (Math.hypot(hx-cx2, hy-cy2) < HANDLE + 3) return 'nwse-resize'
      }
      if (Math.abs(hy - by) < HANDLE + 3 && hx > bx + HANDLE && hx < bx + w - HANDLE) return 'ns-resize'
      if (Math.abs(hy - (by+h)) < HANDLE + 3 && hx > bx + HANDLE && hx < bx + w - HANDLE) return 'ns-resize'
      if (Math.abs(hx - bx) < HANDLE + 3 && hy > by + HANDLE && hy < by + h - HANDLE) return 'ew-resize'
      if (Math.abs(hx - (bx+w)) < HANDLE + 3 && hy > by + HANDLE && hy < by + h - HANDLE) return 'ew-resize'
      if (hx > bx && hx < bx+w && hy > by && hy < by+h) return 'move'
      return 'crosshair'
    }

    const canvasXY = (e) => {
      const rect = annCanvas.value.getBoundingClientRect()
      return {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      }
    }

    const onCvMousedown = (e) => {
      if (e.button !== 0) return
      e.preventDefault()
      const { x, y } = canvasXY(e)

      if (selectedBoxIndex.value >= 0) {
        const box = annotationBoxes.value[selectedBoxIndex.value]
        const [cx, cy, bw, bh] = box.bbox
        const bx = (cx - bw / 2) * dw
        const by = (cy - bh / 2) * dh
        const w = bw * dw
        const h = bh * dh

        const corners = [[bx,by,'tl'],[bx+w,by,'tr'],[bx,by+h,'bl'],[bx+w,by+h,'br']]
        for (const [cx2, cy2, handle] of corners) {
          if (Math.hypot(x-cx2, y-cy2) < HANDLE + 4) {
            drawState = { mode: 'resize', handle, bi: selectedBoxIndex.value, sx: x, sy: y, ox: bx, oy: by, ow: w, oh: h, orig: {...box.bbox} }
            return
          }
        }

        if (x > bx && x < bx+w && y > by && y < by+h) {
          drawState = { mode: 'move', bi: selectedBoxIndex.value, sx: x, sy: y, ox: bx, oy: by, ow: w, oh: h, orig: {...box.bbox} }
          return
        }
      }

      selectedBoxIndex.value = -1
      drawState = { mode: 'new', sx: x, sy: y }
      tempRect = { x, y, w: 0, h: 0 }
    }

    const onCvMousemove = (e) => {
      const { x, y } = canvasXY(e)
      mousePos = { x, y }

      if (!drawState) {
        redrawAnn()
        return
      }

      if (drawState.mode === 'new') {
        tempRect = {
          x: Math.min(drawState.sx, x),
          y: Math.min(drawState.sy, y),
          w: Math.abs(x - drawState.sx),
          h: Math.abs(y - drawState.sy)
        }
      } else if (drawState.mode === 'move') {
        const bi = drawState.bi
        const dx = x - drawState.sx
        const dy = y - drawState.sy
        const box = annotationBoxes.value[bi]
        const [cx, cy, bw, bh] = drawState.orig
        const newCx = cx + dx / dw
        const newCy = cy + dy / dh
        const newBbox = [
          Math.max(bw/2, Math.min(1-bw/2, newCx)),
          Math.max(bh/2, Math.min(1-bh/2, newCy)),
          bw, bh
        ]
        annotationBoxes.value[bi] = { ...box, bbox: newBbox }
      } else if (drawState.mode === 'resize') {
        const bi = drawState.bi
        const { handle, orig } = drawState
        const [cx, cy, bw, bh] = orig
        let newBbox = [...orig]

        if (handle === 'tl') {
          const dw2 = (drawState.ox - x) / dw
          const dh2 = (drawState.oy - y) / dh
          newBbox = [cx - dw2/2, cy - dh2/2, Math.max(0.01, bw + dw2), Math.max(0.01, bh + dh2)]
        } else if (handle === 'tr') {
          const dw2 = (x - (drawState.ox + drawState.ow)) / dw
          const dh2 = (drawState.oy - y) / dh
          newBbox = [cx + dw2/2, cy - dh2/2, Math.max(0.01, bw + dw2), Math.max(0.01, bh + dh2)]
        } else if (handle === 'bl') {
          const dw2 = (drawState.ox - x) / dw
          const dh2 = (y - (drawState.oy + drawState.oh)) / dh
          newBbox = [cx - dw2/2, cy + dh2/2, Math.max(0.01, bw + dw2), Math.max(0.01, bh + dh2)]
        } else if (handle === 'br') {
          const dw2 = (x - (drawState.ox + drawState.ow)) / dw
          const dh2 = (y - (drawState.oy + drawState.oh)) / dh
          newBbox = [cx + dw2/2, cy + dh2/2, Math.max(0.01, bw + dw2), Math.max(0.01, bh + dh2)]
        }

        newBbox[0] = Math.max(newBbox[2]/2, Math.min(1 - newBbox[2]/2, newBbox[0]))
        newBbox[1] = Math.max(newBbox[3]/2, Math.min(1 - newBbox[3]/2, newBbox[1]))
        newBbox = newBbox.map(v => Math.round(v * 1e6) / 1e6)
        annotationBoxes.value[bi] = { ...annotationBoxes.value[bi], bbox: newBbox }
      }

      redrawAnn()
    }

    const onCvMouseup = (e) => {
      if (!drawState) return
      if (drawState.mode === 'new' && tempRect && tempRect.w > 5 && tempRect.h > 5) {
        const bbox = [
          Math.round(((tempRect.x + tempRect.w/2) / dw) * 1e6) / 1e6,
          Math.round(((tempRect.y + tempRect.h/2) / dh) * 1e6) / 1e6,
          Math.round((tempRect.w / dw) * 1e6) / 1e6,
          Math.round((tempRect.h / dh) * 1e6) / 1e6,
        ]
        annotationBoxes.value.push({
          class_id: currentClassId.value,
          class_name: availableClasses.value[currentClassId.value] || `class_${currentClassId.value}`,
          bbox
        })
        selectedBoxIndex.value = annotationBoxes.value.length - 1
        tempRect = null
      }
      drawState = null
      redrawAnn()
    }

    const onCvMouseleave = () => {
      mousePos = null
      if (drawState && drawState.mode === 'new') {
        tempRect = null
        drawState = null
        redrawAnn()
      }
    }

    const selectBox = (i) => {
      selectedBoxIndex.value = i
      if (i >= 0) currentClassId.value = annotationBoxes.value[i].class_id
      redrawAnn()
    }

    const deleteBox = (i) => {
      annotationBoxes.value.splice(i, 1)
      if (selectedBoxIndex.value === i) selectedBoxIndex.value = -1
      else if (selectedBoxIndex.value > i) selectedBoxIndex.value--
      redrawAnn()
    }

    const cancelAnnotate = () => {
      annotatingImage.value = null
      annotationBoxes.value = []
      selectedBoxIndex.value = -1
      drawState = null
      tempRect = null
      mousePos = null
      document.removeEventListener('keydown', onAnnKeydown)
    }

    watch(annotationBoxes, () => { nextTick(() => redrawAnn()) }, { deep: true })
    watch(selectedBoxIndex, () => { nextTick(() => redrawAnn()) })

    const onAnnKeydown = (e) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedBoxIndex.value >= 0) {
          deleteBox(selectedBoxIndex.value)
        }
      }
      if (e.key === 'Escape') {
        selectedBoxIndex.value = -1
        redrawAnn()
      }
    }

    const saveAnnotations = async () => {
      savingAnnotations.value = true
      await new Promise(r => setTimeout(r, 500))
      savingAnnotations.value = false
      ElMessage.success(`已保存 ${annotationBoxes.value.length} 个标注`)
      cancelAnnotate()
      await loadDataset()
    }

    const selectImage = (img) => {
      selectedImage.value = img
      allCurrentImages.value = filteredImages.value
      currentImageIndex.value = allCurrentImages.value.findIndex(i => i.id === img.id)
      showImageDialog.value = true
      highlightedBbox.value = -1
      nextTick(() => { if (detailImgRef.value && bboxCanvas.value) drawBboxes() })
    }

    const prevImage = () => {
      if (currentImageIndex.value > 0) {
        currentImageIndex.value--
        selectedImage.value = allCurrentImages.value[currentImageIndex.value]
        highlightedBbox.value = -1
        nextTick(() => { if (detailImgRef.value && bboxCanvas.value) drawBboxes() })
      }
    }

    const nextImage = () => {
      if (currentImageIndex.value < allCurrentImages.value.length - 1) {
        currentImageIndex.value++
        selectedImage.value = allCurrentImages.value[currentImageIndex.value]
        highlightedBbox.value = -1
        nextTick(() => { if (detailImgRef.value && bboxCanvas.value) drawBboxes() })
      }
    }

    const getDatasetImageCount = (dsId) => {
      const ds = datasetList.value.find(d => d.id === dsId)
      return ds ? ds.total_images : 0
    }

    const onImageLoad = () => { nextTick(() => drawBboxes()) }
    const onImgError = (e) => { e.target.style.display = 'none' }

    const drawBboxes = () => {
      const canvas = bboxCanvas.value
      const img = detailImgRef.value
      if (!canvas || !img || !selectedImage.value) return
      const rect = img.getBoundingClientRect()
      canvas.width = rect.width
      canvas.height = rect.height
      const ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      selectedImage.value.boxes?.forEach((box, i) => {
        const color = getBboxColor(box.class_id)
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
        const label = `${box.class_name}`
        ctx.fillRect(x, y - 18 > 0 ? y - 18 : 0, ctx.measureText(label).width + 8, 18)
        ctx.globalAlpha = 1
        ctx.fillStyle = '#fff'
        ctx.font = 'bold 12px sans-serif'
        ctx.fillText(label, x + 4, y - 5 > 0 ? y - 5 : 12)
      })
      ctx.globalAlpha = 1
    }

    const getBboxColor = (classId) => COLORS[(classId || 0) % COLORS.length]
    const highlightBbox = (i) => { highlightedBbox.value = i; drawBboxes() }
    const unhighlightBbox = () => { highlightedBbox.value = -1; drawBboxes() }
    const getYoloFormat = (img) => img.boxes?.map(b => `${b.class_id} ${b.bbox.map(v => v.toFixed(6)).join(' ')}`).join('\n') || '# 无标注'

    // 上传
    const onFileChange = (file, files) => { fileList.value = files }
    const onFileRemove = (file, files) => { fileList.value = files }
    const submitUpload = async () => {
      if (fileList.value.length === 0) { ElMessage.warning('请选择图片'); return }
      uploading.value = true
      try {
        const formData = new FormData()
        fileList.value.forEach(f => { formData.append('files', f.raw) })
        const res = await fetch(`${API}/datasets/upload-images?dataset_id=${currentDatasetId.value}`, { method: 'POST', body: formData })
        const data = await res.json()
        if (data.success) {
          ElMessage.success(`成功上传 ${data.uploaded_count} 张图片`)
          showUploadDialog.value = false
          fileList.value = []
          await loadDataset()
        } else {
          ElMessage.error(data.message || '上传失败')
        }
      } catch (e) {
        ElMessage.error('上传失败: ' + e.message)
      } finally {
        uploading.value = false
      }
    }

    const deleteImage = async (img) => {
      try {
        await ElMessageBox.confirm(`确定删除 ${img.filename}？`, '确认')
        const res = await fetch(`${API}/datasets/image/${img.id}`, { method: 'DELETE' })
        const data = await res.json()
        if (data.success) {
          ElMessage.success('已删除')
          showImageDialog.value = false
          await loadDataset()
        } else {
          ElMessage.error(data.message || '删除失败')
        }
      } catch (e) {
        if (e !== 'cancel') ElMessage.error('删除失败')
      }
    }

    watch(showImageDialog, (val) => {
      if (val) { nextTick(() => { window.addEventListener('resize', drawBboxes) }) }
      else { window.removeEventListener('resize', drawBboxes) }
    })

    return {
      datasetInfo, loading, loadingImages, loadingDatasetList, loadError, activeTab, filterSplit, searchText, showImageDialog, showUploadDialog, uploading,
      fileList, selectedImage, canvasWrapper, bboxCanvas, detailImgRef, highlightedBbox,
      autoLabelTask, autoLabelClasses, newClassName, autoLabelRunning, autoLabelSteps, autoLabelResults,
      autoLabelDatasetId, tabs,
      annotatingImage, annotationBoxes, selectedBoxIndex, currentClassId,
      savingAnnotations, availableClasses,
      filteredImages, allImagesForAnnotate, totalObjects,
      datasetList, currentDatasetId, showImportDialog, showMergeDialog, importing, merging,
      addClass, removeClass, runAutoLabel, applyAutoLabelResults, clearAutoLabel,
      startAnnotate, onAnnImgLoad,
      onCvMousedown, onCvMousemove, onCvMouseup, onCvMouseleave,
      selectBox, deleteBox, cancelAnnotate, saveAnnotations,
      selectImage, prevImage, nextImage, getDatasetImageCount,
      onImageLoad, onImgError, drawBboxes, getBboxColor, highlightBbox, unhighlightBbox, getYoloFormat,
      onFileChange, onFileRemove, submitUpload, deleteImage, COLORS,
      loadDatasetList, loadDataset, onDatasetChange, switchToDataset, switchTab, onImportFileChange, onImportFileRemove,
      doImportDataset, confirmMerge, doMergeDataset,
    }
  }
}
</script>

<style scoped>
.datasets-view {
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

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* Tab 切换栏 */
.tabs-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  background: white;
  padding: 16px 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.tab-btn-active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
}

.tab-icon {
  margin-right: 6px;
}

.tab-badge {
  margin-left: 6px;
}

/* 浏览面板 */
.browse-panel {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

/* 数据集统计 */
.dataset-stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 10px;
}

.stat-icon {
  font-size: 28px;
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
}

.stat-label {
  font-size: 12px;
  color: #666;
}

.classes-card {
  grid-column: span 2;
}

.class-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.classes-label {
  font-size: 12px;
  color: #666;
  margin-right: 4px;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.filter-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-label {
  font-size: 13px;
  color: #666;
}

/* 加载/错误/空状态 */
.loading-state,
.error-state,
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.error-state {
  color: #f56c6c;
}

.error-icon,
.empty-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 16px;
}

.empty-hint {
  font-size: 13px;
  margin-top: 8px;
}

/* 图片网格 */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.image-card {
  cursor: pointer;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #eee;
  transition: all 0.2s;
}

.image-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  border-color: #667eea;
}

.image-wrapper {
  position: relative;
  width: 100%;
  padding-top: 75%;
  background: #f5f5f5;
  overflow: hidden;
}

.image-wrapper img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0,0,0,0.6));
  padding: 5px 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.image-card:hover .image-overlay {
  opacity: 1;
}

.obj-count {
  color: white;
  font-size: 12px;
}

.split-badge {
  position: absolute;
  top: 5px;
  right: 5px;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  color: white;
  font-weight: 600;
}

.split-badge.train {
  background: #67c23a;
}

.split-badge.val {
  background: #e6a23c;
}

.annotated-badge {
  position: absolute;
  top: 5px;
  left: 5px;
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(103, 194, 58, 0.9);
  color: white;
  font-weight: 600;
}

.image-info {
  padding: 6px 8px;
  background: white;
}

.filename {
  font-size: 11px;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

/* 详情弹窗 */
.image-detail {
  display: flex;
  gap: 20px;
  height: calc(100vh - 200px);
}

.detail-image-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a1a1a;
  border-radius: 8px;
  overflow: hidden;
}

.canvas-wrapper {
  position: relative;
  max-width: 100%;
  max-height: 100%;
}

.detail-img {
  max-width: 100%;
  max-height: calc(100vh - 220px);
  display: block;
  margin: auto;
}

.bbox-canvas {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.detail-info-panel {
  width: 280px;
  overflow-y: auto;
}

.detail-info-panel h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #333;
}

.bbox-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 300px;
  overflow-y: auto;
}

.bbox-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: #f5f7fa;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.bbox-item:hover {
  background: #ecf5ff;
}

.bbox-color-bar {
  width: 4px;
  height: 30px;
  border-radius: 2px;
  background: var(--bbox-color, #409eff);
  flex-shrink: 0;
}

.bbox-info {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.bbox-class {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.bbox-id {
  font-size: 11px;
  color: #999;
}

.bbox-coords {
  font-size: 10px;
  color: #888;
  font-family: 'Consolas', monospace;
  white-space: nowrap;
}

.yolo-format {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  font-family: 'Consolas', monospace;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
}

/* 自动标注 */
.pipeline-container {
  margin-top: 20px;
}

.pipeline-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pipeline-step {
  display: flex;
  gap: 12px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.pipeline-step.running {
  background: #ecf5ff;
  border: 1px solid #409eff;
}

.pipeline-step.done {
  background: #f0f9eb;
  border: 1px solid #67c23a;
}

.step-indicator {
  font-size: 20px;
  flex-shrink: 0;
  width: 30px;
  text-align: center;
}

.step-content {
  flex: 1;
}

.step-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 5px;
}

.step-desc {
  font-size: 13px;
  color: #666;
}

.step-progress {
  margin-top: 8px;
}

.results-section {
  margin-top: 25px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 12px;
}

.result-preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
  margin-top: 15px;
}

.result-card {
  display: flex;
  gap: 10px;
  padding: 12px;
  background: white;
  border-radius: 8px;
  border: 1px solid #eee;
}

.result-color-bar {
  width: 4px;
  border-radius: 2px;
  background: var(--result-color);
  flex-shrink: 0;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.result-class {
  font-weight: 600;
  font-size: 14px;
}

.result-conf {
  font-size: 12px;
  color: #67c23a;
}

.result-bbox {
  font-size: 10px;
  color: #999;
  font-family: monospace;
}

/* 手动标注 */
.annotate-workspace {
  margin-top: 15px;
}

.annotate-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.annotate-content {
  display: flex;
  gap: 15px;
  align-items: flex-start;
}

/* Canvas 标注区 */
.canvas-wrap {
  position: relative;
  display: inline-block;
  line-height: 0;
  background: #1a1a1a;
  border-radius: 8px;
  overflow: hidden;
}

.ann-img {
  display: block;
  max-width: 100%;
  user-select: none;
  -webkit-user-drag: none;
}

.ann-canvas {
  position: absolute;
  top: 0;
  left: 0;
  cursor: crosshair;
}

/* 侧边栏 */
.ann-sidebar {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.ann-section {
  background: white;
  border: 1px solid #eee;
  border-radius: 10px;
  padding: 12px;
}

.ann-section-title {
  font-size: 13px;
  font-weight: 700;
  color: #333;
  margin-bottom: 10px;
}

.ann-class-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
  border: 2px solid transparent;
  margin-bottom: 4px;
}

.ann-class-btn:hover {
  background: #f5f7fa;
}

.ann-class-btn.active {
  background: color-mix(in srgb, var(--c) 12%, white);
  border-color: var(--c);
  font-weight: 600;
}

.ann-cls-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ann-box-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
  max-height: 360px;
  overflow-y: auto;
}

.ann-box-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
  border: 2px solid transparent;
}

.ann-box-item:hover {
  background: #f5f7fa;
}

.ann-box-item.selected {
  background: color-mix(in srgb, var(--c) 12%, white);
  border-color: var(--c);
}

.ann-box-num {
  width: 20px;
  height: 20px;
  background: var(--c);
  color: white;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ann-box-name {
  flex: 1;
  font-weight: 500;
}

.ann-box-del {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fee;
  color: #f56c6c;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
}

.ann-box-item:hover .ann-box-del {
  opacity: 1;
}
</style>
