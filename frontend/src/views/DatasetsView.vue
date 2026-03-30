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
              <span class="img-count">{{ filteredImages.length }} 张</span>
              <el-radio-group v-model="imageSplitFilter" size="small">
                <el-radio-button label="all">全部</el-radio-button>
                <el-radio-button label="train">训练</el-radio-button>
                <el-radio-button label="val">验证</el-radio-button>
                <el-radio-button label="test">测试</el-radio-button>
              </el-radio-group>
              <el-select v-model="imageStatusFilter" size="small" style="width: 100px">
                <el-option label="全部" value="all" />
                <el-option label="已标注" value="annotated" />
                <el-option label="未标注" value="unannotated" />
              </el-select>
            </div>
            <div class="toolbar-right">
              <el-button size="small" @click="showVideoDialog = true; videoDatasetId = currentDatasetId">视频抽帧</el-button>
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
              v-for="img in filteredImages"
              :key="img.id"
              class="image-card"
              :class="{ selected: selectedImage?.id === img.id }"
              @click="openImage(img)"
            >
              <div class="image-thumb">
                <img :src="img.url" :alt="img.filename" @error="onImgError" />
                <span class="split-badge" :class="'split-' + img.split">{{ img.split }}</span>
                <span class="ann-badge" :class="(img.num_objects || img.boxes?.length || 0) > 0 ? 'ann-yes' : 'ann-no'">
                  {{ (img.num_objects || img.boxes?.length || 0) > 0 ? '✓' : '○' }}
                </span>
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

      <!-- Label Studio Tab -->
      <el-tab-pane label="Label Studio" name="labelstudio">
        <div class="ls-panel">
          <!-- Connection Settings -->
          <div class="ls-section">
            <h4 class="ls-section-title">🔗 Label Studio 连接</h4>
            <div class="ls-connection-form">
              <div class="ls-form-row">
                <el-input
                  v-model="lsUrl"
                  placeholder="http://localhost:8080"
                  style="flex: 1"
                >
                  <template #prepend>地址</template>
                </el-input>
                <el-input
                  v-model="lsApiKey"
                  placeholder="API Key"
                  style="flex: 1"
                  show-password
                >
                  <template #prepend>密钥</template>
                </el-input>
                <el-button type="primary" @click="testLsConnection" :loading="lsTesting">
                  测试连接
                </el-button>
              </div>
              <div v-if="lsStatus" class="ls-status-info" :class="lsStatus.connected ? 'connected' : 'disconnected'">
                <span v-if="lsStatus.connected">
                  ✅ 已连接 Label Studio | 用户: {{ lsStatus.user?.email || 'unknown' }} | 项目数: {{ lsStatus.project_count }}
                </span>
                <span v-else>
                  ❌ {{ lsStatus.error || '连接失败' }}
                </span>
              </div>
            </div>
          </div>

          <!-- Sync Dataset -->
          <div class="ls-section" v-if="lsStatus?.connected">
            <h4 class="ls-section-title">📤 同步到 Label Studio</h4>
            <div class="ls-sync-form">
              <el-form label-position="top">
                <el-form-item label="选择数据集">
                  <el-select v-model="lsDatasetId" style="width: 100%">
                    <el-option
                      v-for="ds in datasets"
                      :key="ds.id"
                      :label="ds.name + ' (' + (ds.total_images || 0) + '张)'"
                      :value="ds.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="数据集名称（Label Studio 项目名）">
                  <el-input v-model="lsProjectName" placeholder="将作为 LS 项目名称" />
                </el-form-item>
                <el-form-item label="检测类别">
                  <el-input v-model="lsClassNames" placeholder="person, helmet, no_helmet（逗号分隔）" />
                </el-form-item>
                <div style="display: flex; gap: 12px">
                  <el-form-item label="导入哪个划分" style="flex: 1">
                    <el-select v-model="lsSplit" style="width: 100%">
                      <el-option label="训练集 (train)" value="train" />
                      <el-option label="验证集 (val)" value="val" />
                      <el-option label="测试集 (test)" value="test" />
                    </el-select>
                  </el-form-item>
                </div>
              </el-form>
              <el-button
                type="success"
                :loading="lsSyncing"
                @click="syncToLs"
                :disabled="!lsDatasetId || !lsClassNames"
                style="width: 100%; margin-top: 8px"
              >
                {{ lsSyncing ? '同步中...' : '🚀 一键同步到 Label Studio' }}
              </el-button>

              <!-- Sync Result -->
              <div v-if="lsSyncResult" class="ls-sync-result" :class="lsSyncResult.success ? 'success' : 'error'">
                <div v-if="lsSyncResult.success">
                  <p>✅ {{ lsSyncResult.message }}</p>
                  <p>📊 已导入: {{ lsSyncResult.imported }} 张 | 总任务: {{ lsSyncResult.total_tasks }}</p>
                  <el-button type="primary" size="small" @click="openLsProject(lsSyncResult.project_id)">
                    🎯 前往 Label Studio 标注
                  </el-button>
                </div>
                <div v-else>
                  <p>❌ {{ lsSyncResult.error || '同步失败' }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Existing Projects -->
          <div class="ls-section" v-if="lsStatus?.connected">
            <h4 class="ls-section-title">📁 Label Studio 项目</h4>
            <el-button size="small" @click="loadLsProjects" :loading="lsLoadingProjects" style="margin-bottom: 12px">
              刷新列表
            </el-button>
            <div v-if="lsProjects.length === 0 && !lsLoadingProjects" class="ls-empty">
              暂无项目，请先同步数据集
            </div>
            <div v-else class="ls-projects">
              <div v-for="proj in lsProjects" :key="proj.id" class="ls-project-card">
                <div class="project-info">
                  <span class="project-name">{{ proj.name }}</span>
                  <span class="project-url">{{ proj.url }}</span>
                </div>
                <div class="project-actions">
                  <el-button size="small" type="primary" @click="openLsProject(proj.id)">
                    打开标注
                  </el-button>
                  <el-button size="small" type="success" @click="exportLsAnnotations(proj.id)">
                    导出标注
                  </el-button>
                </div>
              </div>
            </div>
          </div>

          <!-- Not Connected State -->
          <div v-if="!lsStatus?.connected && !lsTesting" class="ls-not-connected">
            <div class="ls-not-connected-icon">🏷️</div>
            <h4>未连接到 Label Studio</h4>
            <p>请在上方输入 Label Studio 地址和 API Key，然后点击"测试连接"</p>
            <p class="ls-hint">
              推荐使用 Docker 运行 Label Studio:<br>
              <code>docker run -p 8080:8080 heartexlabs/label-studio</code>
            </p>
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
      <div style="margin-bottom: 12px; font-size: 13px; color: var(--color-text-muted)">
        目标数据集：<strong>{{ datasets.find(d => d.id === currentDatasetId)?.name || currentDatasetId }}</strong>
        <br><span style="font-size: 12px">支持 JPG、PNG、WebP 图片或 ZIP 压缩包（自动解压）</span>
      </div>
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :limit="100"
        :on-change="onFileChange"
        :on-remove="onFileRemove"
        multiple
        accept="image/*,.zip"
        style="width: 100%"
      >
        <div class="upload-content">
          <div class="upload-icon">📤</div>
          <div class="upload-text">拖拽图片或 ZIP 到此处，或点击上传</div>
          <div class="upload-hint">ZIP 内图片将自动解压并分配到训练集</div>
        </div>
      </el-upload>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload" :disabled="fileList.length === 0">
          上传 {{ fileList.length }} 个{{ zipFileCount > 0 ? '（含ZIP）' : '' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Video Extract Dialog -->
    <el-dialog v-model="showVideoDialog" title="视频抽帧导入" width="520px" destroy-on-close>
      <el-alert type="info" :closable="false" style="margin-bottom: 16px">
        上传视频文件，系统将按帧间隔自动抽取图片帧，导入到数据集中。支持 MP4/AVI/MOV/MKV 格式。
      </el-alert>
      <el-form label-position="top">
        <el-form-item label="目标数据集">
          <el-select v-model="videoDatasetId" style="width: 100%">
            <el-option
              v-for="ds in datasets"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="视频文件">
          <el-upload
            ref="videoUploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            :on-change="onVideoFileChange"
            :on-remove="onVideoFileRemove"
            accept="video/*"
            style="width: 100%"
          >
            <div class="upload-content">
              <div class="upload-icon">🎬</div>
              <div class="upload-text">拖拽视频到此处，或点击上传</div>
              <div class="upload-hint">支持 MP4、AVI、MOV、MKV</div>
            </div>
          </el-upload>
        </el-form-item>
        <div style="display: flex; gap: 12px">
          <el-form-item label="抽帧间隔" style="flex: 1">
            <el-input-number v-model="videoFrameInterval" :min="1" :max="100" style="width: 100%" />
          </el-form-item>
          <el-form-item label="最大帧数" style="flex: 1">
            <el-input-number v-model="videoMaxFrames" :min="1" :max="2000" style="width: 100%" />
          </el-form-item>
          <el-form-item label="保存到" style="flex: 1">
            <el-select v-model="videoSplit" style="width: 100%">
              <el-option label="训练集" value="train" />
              <el-option label="验证集" value="val" />
              <el-option label="测试集" value="test" />
            </el-select>
          </el-form-item>
        </div>
        <div class="video-hint">
          每隔 <strong>{{ videoFrameInterval }}</strong> 帧抽 1 张，最多 <strong>{{ videoMaxFrames }}</strong> 张
        </div>
      </el-form>

      <!-- Video results -->
      <div v-if="videoResults" class="video-results">
        <el-alert :type="videoResults.success ? 'success' : 'error'" :closable="false">
          {{ videoResults.message }}
        </el-alert>
        <div v-if="videoResults.video_info" class="video-info">
          <span>总帧数: {{ videoResults.video_info.total_frames }}</span>
          <span>帧率: {{ videoResults.video_info.fps }} fps</span>
          <span>时长: {{ videoResults.video_info.duration_sec }}s</span>
          <span>分辨率: {{ videoResults.video_info.resolution }}</span>
        </div>
      </div>

      <template #footer>
        <el-button @click="showVideoDialog = false">取消</el-button>
        <el-button type="primary" :loading="extractingVideo" @click="submitVideoExtract" :disabled="!videoFile">
          {{ extractingVideo ? '抽帧中...' : '开始抽帧' }}
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
            <span class="tool-hint" v-else>点击图片查看大图</span>
            <div class="zoom-controls">
              <el-button size="small" text @click="zoomOut" title="缩小">−</el-button>
              <span class="zoom-level">{{ Math.round(zoom * 100) }}%</span>
              <el-button size="small" text @click="zoomIn" title="放大">+</el-button>
              <el-button size="small" text @click="zoomReset" title="重置">⟲</el-button>
            </div>
          </div>
          <div
            class="canvas-container"
            ref="canvasContainer"
            @mousedown="onCanvasMouseDown"
            @mousemove="onCanvasMouseMove"
            @mouseup="onCanvasMouseUp"
            @mouseleave="onCanvasMouseUp"
            @wheel.prevent="onCanvasWheel"
            :style="{ cursor: annotationMode ? 'crosshair' : 'default' }"
          >
            <div class="img-wrapper" ref="imgWrapper" :style="imgWrapperStyle">
              <img
                ref="detailImgRef"
                :src="selectedImage.url"
                class="detail-img"
                @load="onImageLoad"
                crossorigin="anonymous"
                draggable="false"
              />
              <canvas ref="bboxCanvas" class="bbox-canvas"></canvas>
            </div>
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
                <span class="bbox-class">{{ getClassDisplayName(box) }}</span>
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

          <!-- Class Management -->
          <h4 style="margin-top: 16px">类别管理</h4>
          <div class="class-manager">
            <div class="class-tags">
              <el-tag
                v-for="(cls, i) in datasetClasses"
                :key="i"
                closable
                @close="removeClass(i)"
                :type="selectedClassId === i ? 'primary' : 'info'"
                @click="selectedClassId = i"
                class="class-tag"
              >
                {{ cls }}
              </el-tag>
              <span v-if="datasetClasses.length === 0" class="no-classes">暂无类别</span>
            </div>
            <div class="class-add">
              <el-input v-model="newClassName" size="small" placeholder="类名" style="width: 90px" @keyup.enter="addClass" />
              <el-button size="small" @click="addClass">添加</el-button>
            </div>
          </div>

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
        <div class="detail-footer">
          <div class="nav-buttons">
            <el-button size="small" :disabled="currentImageIndex <= 0" @click="goToPrevImage">← 上一张</el-button>
            <span class="nav-indicator">{{ currentImageIndex + 1 }} / {{ filteredImages.length }}</span>
            <el-button size="small" :disabled="currentImageIndex >= filteredImages.length - 1" @click="goToNextImage">下一张 →</el-button>
          </div>
          <el-button size="small" @click="showImageDialog = false">关闭</el-button>
        </div>
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
  getDatasetMeta,
  updateDatasetMeta,
  getDemoDataset,
  createDataset,
  deleteDataset,
  uploadImages,
  deleteImage,
  saveImageAnnotations,
  autoLabelDinoSam,
  getAutoLabelInfo,
  extractVideoFrames,
} from '../api/datasets'
import {
  lsConnect,
  lsListProjects,
  lsSyncDataset,
  lsOpenProject,
  lsExportAnnotations,
} from '../api/labelStudio'

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

// Video extraction
const showVideoDialog = ref(false)
const videoFile = ref(null)
const videoFileList = ref([])
const extractingVideo = ref(false)
const videoFrameInterval = ref(5)
const videoMaxFrames = ref(200)
const videoSplit = ref('train')
const videoResults = ref(null)
const videoDatasetId = ref(null)
const videoUploadRef = ref(null)

// Label Studio
const lsUrl = ref('http://localhost:8080')
const lsApiKey = ref('')
const lsTesting = ref(false)
const lsStatus = ref(null)
const lsSyncing = ref(false)
const lsSyncResult = ref(null)
const lsDatasetId = ref(null)
const lsProjectName = ref('')
const lsClassNames = ref('')
const lsSplit = ref('train')
const lsProjects = ref([])
const lsLoadingProjects = ref(false)

// Dataset cards
const availableClasses = ref(['person', 'bicycle', 'car', 'motorcycle', 'airplane'])

// Image detail / annotation state
const detailImgRef = ref(null)
const bboxCanvas = ref(null)
const canvasContainer = ref(null)
const imgWrapper = ref(null)
const highlightedBbox = ref(-1)
const selectedBbox = ref(-1)
const localBoxes = ref([])
const annotationMode = ref(false)
const selectedClassId = ref(0)
const savingAnnotations = ref(false)

// Image navigation
const currentImageIndex = ref(-1)

// Class management
const datasetClasses = ref([])   // 当前数据集的类名列表
const newClassName = ref('')     // 新增类名输入

// Zoom state
const zoom = ref(1)
const zoomMin = 0.2
const zoomMax = 5
const imgWrapperStyle = computed(() => ({
  transform: `scale(${zoom.value})`,
  transformOrigin: 'center center',
  display: 'inline-block',
  transition: 'transform 0.1s ease',
}))

// Image filter state
const imageSplitFilter = ref('all')
const imageStatusFilter = ref('all')

const filteredImages = computed(() => {
  return images.value.filter(img => {
    const splitMatch = imageSplitFilter.value === 'all' || img.split === imageSplitFilter.value
    const annotated = (img.num_objects || img.boxes?.length || 0) > 0
    const statusMatch = imageStatusFilter.value === 'all' ||
      (imageStatusFilter.value === 'annotated' && annotated) ||
      (imageStatusFilter.value === 'unannotated' && !annotated)
    return splitMatch && statusMatch
  })
})

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

function onVideoFileChange(file, files) {
  videoFileList.value = files
  videoFile.value = file.raw
}

function onVideoFileRemove(file, files) {
  videoFileList.value = files
  videoFile.value = null
}

async function submitVideoExtract() {
  if (!videoFile.value) {
    ElMessage.warning('请选择视频文件')
    return
  }
  if (!videoDatasetId.value) {
    ElMessage.warning('请选择目标数据集')
    return
  }
  extractingVideo.value = true
  videoResults.value = null
  try {
    const res = await extractVideoFrames(
      videoDatasetId.value,
      videoFile.value,
      videoFrameInterval.value,
      videoMaxFrames.value,
      videoSplit.value
    )
    videoResults.value = res
    if (res.success) {
      ElMessage.success(res.message)
      showVideoDialog.value = false
      videoFile.value = null
      videoFileList.value = []
      videoResults.value = null
      await loadImages()
    } else {
      ElMessage.error(res.message || '抽帧失败')
    }
  } catch (e) {
    ElMessage.error('抽帧失败: ' + e.message)
  } finally {
    extractingVideo.value = false
  }
}

// ============================================
// Label Studio Functions
// ============================================

async function testLsConnection() {
  lsTesting.value = true
  lsStatus.value = null
  try {
    const res = await lsConnect(lsUrl.value, lsApiKey.value)
    lsStatus.value = res
    if (res.connected) {
      ElMessage.success('连接成功')
      await loadLsProjects()
    } else {
      ElMessage.error(res.error || '连接失败')
    }
  } catch (e) {
    lsStatus.value = { connected: false, error: e.message }
    ElMessage.error('连接测试失败: ' + e.message)
  } finally {
    lsTesting.value = false
  }
}

async function loadLsProjects() {
  lsLoadingProjects.value = true
  try {
    const res = await lsListProjects()
    if (res.success) {
      lsProjects.value = res.projects || []
    } else {
      lsProjects.value = []
    }
  } catch (e) {
    lsProjects.value = []
  } finally {
    lsLoadingProjects.value = false
  }
}

async function syncToLs() {
  if (!lsDatasetId.value) {
    ElMessage.warning('请选择数据集')
    return
  }
  if (!lsClassNames.value.trim()) {
    ElMessage.warning('请输入检测类别')
    return
  }

  lsSyncing.value = true
  lsSyncResult.value = null

  // 获取选中的数据集信息
  const selectedDs = datasets.value.find(d => d.id === lsDatasetId.value)
  const projectName = lsProjectName.value.trim() || (selectedDs?.name + ' LS')

  try {
    const res = await lsSyncDataset({
      dataset_id: lsDatasetId.value,
      dataset_name: projectName,
      class_names: lsClassNames.value.split(',').map(s => s.trim()).filter(Boolean),
      split: lsSplit.value,
      url: lsUrl.value,
      api_key: lsApiKey.value,
    })
    lsSyncResult.value = res
    if (res.success) {
      ElMessage.success(res.message)
      await loadLsProjects()
    } else {
      ElMessage.error(res.error || '同步失败')
    }
  } catch (e) {
    lsSyncResult.value = { success: false, error: e.message }
    ElMessage.error('同步失败: ' + e.message)
  } finally {
    lsSyncing.value = false
  }
}

async function openLsProject(projectId) {
  try {
    const res = await lsOpenProject(projectId)
    if (res.success && res.open_url) {
      window.open(res.open_url, '_blank')
    }
  } catch (e) {
    ElMessage.error('无法打开 Label Studio: ' + e.message)
  }
}

async function exportLsAnnotations(projectId) {
  try {
    const res = await lsExportAnnotations(projectId, {
      output_dir: `/tmp/ls_export_${projectId}`,
      format: 'YOLO',
      url: lsUrl.value,
      api_key: lsApiKey.value,
    })
    if (res.success) {
      ElMessage.success(res.message)
      // Trigger download
      window.open(`/api/label-studio/download-export/${projectId}`, '_blank')
    } else {
      ElMessage.error(res.error || '导出失败')
    }
  } catch (e) {
    ElMessage.error('导出失败: ' + e.message)
  }
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
  localBoxes.value = img.boxes ? img.boxes.map(b => ({...b})) : []

  // Sync datasetClasses from current dataset
  const ds = datasets.value.find(d => d.id === currentDatasetId.value)
  if (ds && ds.class_names && ds.class_names.length > 0 && !ds.class_names.every(c => c.startsWith('class_'))) {
    datasetClasses.value = [...ds.class_names]
  } else {
    // Try to build from existing boxes class names
    const existing = new Set()
    for (const box of (img.boxes || [])) {
      if (box.class_name && !box.class_name.startsWith('class_')) {
        existing.add(box.class_name)
      }
    }
    if (existing.size > 0) {
      datasetClasses.value = [...existing]
    } else if (datasetClasses.value.length === 0) {
      datasetClasses.value = ['object']
    }
  }
  availableClasses.value = [...datasetClasses.value]

  // Set current image index
  currentImageIndex.value = filteredImages.value.findIndex(i => i.id === img.id)

  zoom.value = 1
  showImageDialog.value = true
  nextTick(() => {
    initCanvas()
    drawBboxes()
  })
}

function initCanvas() {
  const canvas = bboxCanvas.value
  const img = detailImgRef.value
  const wrapper = imgWrapper.value
  if (!canvas || !img || !wrapper) return

  const updateCanvas = () => {
    // Canvas size matches the displayed image size
    const rect = img.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = rect.height
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

  // Draw active drawing rect on canvas
  if (isDrawing.value && drawRect.value) {
    const x1 = Math.min(drawRect.value.startX, drawRect.value.endX)
    const y1 = Math.min(drawRect.value.startY, drawRect.value.endY)
    const w = Math.abs(drawRect.value.endX - drawRect.value.startX)
    const h = Math.abs(drawRect.value.endY - drawRect.value.startY)
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 2
    ctx.setLineDash([5, 5])
    ctx.globalAlpha = 1
    ctx.strokeRect(x1, y1, w, h)
    ctx.setLineDash([])
  }
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

function addClass() {
  const name = newClassName.value.trim()
  if (name && !datasetClasses.value.includes(name)) {
    datasetClasses.value.push(name)
    selectedClassId.value = datasetClasses.value.length - 1
    availableClasses.value = [...datasetClasses.value]
    newClassName.value = ''
  }
}

function removeClass(index) {
  datasetClasses.value.splice(index, 1)
  availableClasses.value = [...datasetClasses.value]
  if (selectedClassId.value >= datasetClasses.value.length) {
    selectedClassId.value = Math.max(0, datasetClasses.value.length - 1)
  }
}

function goToNextImage() {
  if (currentImageIndex.value < filteredImages.value.length - 1) {
    currentImageIndex.value++
    openImage(filteredImages.value[currentImageIndex.value])
  }
}

function goToPrevImage() {
  if (currentImageIndex.value > 0) {
    currentImageIndex.value--
    openImage(filteredImages.value[currentImageIndex.value])
  }
}

function zoomIn() {
  zoom.value = Math.min(zoomMax, zoom.value + 0.2)
  redrawAfterZoom()
}

function zoomOut() {
  zoom.value = Math.max(zoomMin, zoom.value - 0.2)
  redrawAfterZoom()
}

function zoomReset() {
  zoom.value = 1
  redrawAfterZoom()
}

function redrawAfterZoom() {
  nextTick(() => {
    initCanvas()
    drawBboxes()
  })
}

function onCanvasWheel(e) {
  if (e.ctrlKey || e.metaKey) {
    const delta = e.deltaY > 0 ? -0.15 : 0.15
    zoom.value = Math.max(zoomMin, Math.min(zoomMax, zoom.value + delta))
    redrawAfterZoom()
  }
}

// Canvas mouse handlers for drawing
function getCanvasCoords(e) {
  const canvas = bboxCanvas.value
  const img = detailImgRef.value
  if (!canvas || !img) return { x: 0, y: 0 }

  const rect = img.getBoundingClientRect()
  // img is centered in canvas via flexbox, so rect reflects actual display area
  const x = (e.clientX - rect.left) * (canvas.width / rect.width)
  const y = (e.clientY - rect.top) * (canvas.height / rect.height)

  return { x, y }
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
  drawBboxes()
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

function getClassDisplayName(box) {
  if (!box) return 'unknown'
  // If we have a class_name that isn't a synthetic "class_N", use it
  if (box.class_name && !box.class_name.startsWith('class_')) {
    return box.class_name
  }
  // Fall back to availableClasses list
  const cid = box.class_id ?? 0
  return availableClasses.value[cid] || `class_${cid}`
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
    zoom.value = 1
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

.video-hint {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  text-align: center;
  margin-top: -8px;
}

.video-results {
  margin-top: var(--space-4);
}

.video-info {
  display: flex;
  gap: var(--space-4);
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  flex-wrap: wrap;
}

.video-info span {
  white-space: nowrap;
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
  flex-wrap: wrap;
}

.tool-hint {
  font-size: var(--text-xs);
  color: #888;
}

.zoom-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.zoom-level {
  font-size: var(--text-xs);
  color: #888;
  min-width: 40px;
  text-align: center;
}

.canvas-container {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
  padding: var(--space-4);
}

.img-wrapper {
  position: relative;
  display: inline-block;
  line-height: 0;
}

.detail-img {
  display: block;
  max-width: 100%;
  max-height: calc(65vh - 120px);
  user-select: none;
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

/* Label Studio Tab */
.ls-panel {
  padding: var(--space-4) 0;
}

.ls-section {
  margin-bottom: var(--space-6);
  padding: var(--space-4);
  background: var(--color-surface-2);
  border-radius: var(--radius-md);
}

.ls-section-title {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  margin-bottom: var(--space-4);
  color: var(--color-text-primary);
}

.ls-connection-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.ls-form-row {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}

.ls-status-info {
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}

.ls-status-info.connected {
  background: rgba(82, 196, 26, 0.1);
  color: var(--color-success);
}

.ls-status-info.disconnected {
  background: rgba(255, 85, 85, 0.1);
  color: var(--color-danger);
}

.ls-sync-form {
  max-width: 600px;
}

.ls-sync-result {
  margin-top: var(--space-4);
  padding: var(--space-4);
  border-radius: var(--radius-sm);
}

.ls-sync-result.success {
  background: rgba(82, 196, 26, 0.1);
  border: 1px solid var(--color-success);
}

.ls-sync-result.error {
  background: rgba(255, 85, 85, 0.1);
  border: 1px solid var(--color-danger);
}

.ls-sync-result p {
  margin-bottom: var(--space-2);
  font-size: var(--text-sm);
}

.ls-empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--text-sm);
}

.ls-projects {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.ls-project-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.project-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.project-name {
  font-weight: var(--font-medium);
  font-size: var(--text-sm);
}

.project-url {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.project-actions {
  display: flex;
  gap: var(--space-2);
}

.ls-not-connected {
  text-align: center;
  padding: var(--space-8);
  color: var(--color-text-muted);
}

.ls-not-connected-icon {
  font-size: 48px;
  margin-bottom: var(--space-4);
}

.ls-not-connected h4 {
  font-size: var(--text-lg);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
}

.ls-not-connected p {
  font-size: var(--text-sm);
  margin-bottom: var(--space-2);
}

.ls-hint {
  margin-top: var(--space-4);
  padding: var(--space-3);
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
}

.ls-hint code {
  font-family: var(--font-mono);
  color: var(--color-primary);
}

/* Split & Annotation Badges */
.split-badge {
  position: absolute;
  top: 4px;
  left: 4px;
  font-size: 9px;
  font-weight: 600;
  padding: 2px 5px;
  border-radius: 3px;
  color: #fff;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.split-train { background: #3B82F6; }
.split-val   { background: #10B981; }
.split-test  { background: #8B5CF6; }

.ann-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #fff;
}

.ann-yes { background: #10B981; }
.ann-no  { background: #94A3B8; }

/* Class Manager */
.class-manager {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.class-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.class-tag {
  cursor: pointer;
}

.no-classes {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  padding: 4px 0;
}

.class-add {
  display: flex;
  gap: 6px;
  align-items: center;
}

/* Detail Dialog Footer / Navigation */
.detail-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.nav-buttons {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-indicator {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  min-width: 60px;
  text-align: center;
}
</style>
