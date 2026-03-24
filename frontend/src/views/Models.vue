<template>
  <div class="models-view">
    <div class="header-actions">
      <h2>🤖 模型仓库</h2>
      <el-button @click="refreshModels">刷新</el-button>
    </div>

    <!-- 模型列表 -->
    <el-table :data="models" stripe style="width: 100%; margin-top: 20px" v-loading="loading">
      <el-table-column prop="name" label="模型名称" min-width="180" />
      <el-table-column prop="task_id" label="关联任务" width="220" show-overflow-tooltip />
      <el-table-column prop="model_type" label="类型" width="100" />
      <el-table-column prop="file_size" label="大小" width="100" />
      <el-table-column label="mAP@50" width="100">
        <template #default="{ row }">
          <span v-if="row.map50" :class="row.map50 >= 0.85 ? 'metric-good' : 'metric-bad'">
            {{ (row.map50 * 100).toFixed(1) }}%
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="mAP@50-95" width="100">
        <template #default="{ row }">
          <span v-if="row.map50_95" :class="row.map50_95 >= 0.65 ? 'metric-good' : 'metric-bad'">
            {{ (row.map50_95 * 100).toFixed(1) }}%
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="部署状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.is_deployed ? 'success' : 'info'" size="small">
            {{ row.is_deployed ? '已部署' : '未部署' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="deployModel(row)" :loading="deploying === row.task_id">
            {{ row.is_deployed ? '已部署' : '部署' }}
          </el-button>
          <el-button size="small" @click="testInference(row)" :disabled="!row.is_deployed">
            测试推理
          </el-button>
          <el-button size="small" type="success" @click="downloadModel(row)">
            下载
          </el-button>
          <el-button size="small" type="warning" @click="exportModel(row)">
            导出ONNX
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="models.length === 0" description="暂无生成的模型，请先创建并完成训练任务" style="margin-top: 60px" />

    <!-- 测试推理对话框 -->
    <el-dialog v-model="showInferDialog" title="模型推理测试" width="800px">
      <div v-if="selectedModel">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 20px">
          <el-descriptions-item label="模型名称">{{ selectedModel.name }}</el-descriptions-item>
          <el-descriptions-item label="任务ID">{{ selectedModel.task_id }}</el-descriptions-item>
          <el-descriptions-item label="mAP@50">
            <span :class="selectedModel.map50 >= 0.85 ? 'metric-good' : 'metric-bad'">
              {{ selectedModel.map50 ? (selectedModel.map50 * 100).toFixed(2) + '%' : '-' }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="推理状态">
            <el-tag :type="selectedModel.is_deployed ? 'success' : 'info'" size="small">
              {{ selectedModel.is_deployed ? '服务中' : '未部署' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <!-- Tab切换: URL / 上传 -->
        <el-tabs v-model="inferTab" style="margin-bottom: 15px">
          <el-tab-pane label="🌐 图片URL" name="url" />
          <el-tab-pane label="📤 图片上传" name="upload" />
        </el-tabs>

        <!-- URL模式 -->
        <div v-if="inferTab === 'url'">
          <el-form label-width="100px">
            <el-form-item label="输入图片">
              <el-input v-model="inferForm.imageUrl" placeholder="输入图片URL或路径，如：http://xxx.jpg" />
            </el-form-item>
            <el-form-item label="批量测试">
              <el-switch v-model="inferForm.batchMode" />
              <span style="margin-left: 10px; color: #999; font-size: 13px">批量从数据集采样测试</span>
            </el-form-item>
          </el-form>
        </div>

        <!-- 上传模式 -->
        <div v-if="inferTab === 'upload'">
          <el-form label-width="100px">
            <el-form-item label="上传图片">
              <el-upload
                ref="uploadRef"
                :auto-upload="false"
                :limit="1"
                accept="image/*"
                :on-change="onUploadChange"
                drag
              >
                <div style="padding: 20px">
                  <el-icon size="32" style="color: #409eff"><upload-filled /></el-icon>
                  <div style="margin-top: 8px; color: #666">拖拽图片到此处，或点击选择文件</div>
                  <div style="color: #999; font-size: 12px; margin-top: 4px">支持 JPG/PNG/BMP，单张不超过 10MB</div>
                </div>
              </el-upload>
            </el-form-item>
          </el-form>
        </div>

        <!-- 推理结果（URL模式） -->
        <div v-if="inferResult && inferTab === 'url'" style="margin-top: 20px">
          <h4>📊 推理结果</h4>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="检测数量">{{ inferResult.total_detections }} 个目标</el-descriptions-item>
            <el-descriptions-item label="平均耗时">{{ inferResult.avg_time_ms?.toFixed(2) || '-' }} ms</el-descriptions-item>
          </el-descriptions>
          <div class="infer-results" v-if="inferResult.results">
            <div v-for="(r, i) in inferResult.results.slice(0, 6)" :key="i" class="infer-result-card">
              <div class="infer-result-path">{{ r.image_path }}</div>
              <div class="infer-result-count">
                检测到 <strong>{{ r.detection_count }}</strong> 个目标
              </div>
              <div class="infer-result-time">{{ r.inference_time_ms?.toFixed(1) }} ms</div>
            </div>
          </div>
        </div>

        <!-- 推理结果（上传模式）: 带标注框的图片 -->
        <div v-if="annotatedImageUrl && inferTab === 'upload'" style="margin-top: 20px">
          <h4>🔍 检测结果</h4>
          <div style="text-align: center; border: 1px solid #e4e7ed; border-radius: 8px; overflow: hidden">
            <img :src="annotatedImageUrl" alt="检测结果" style="max-width: 100%; display: block" />
          </div>
          <div v-if="uploadInferResult && uploadInferResult.detections" style="margin-top: 10px">
            <el-tag v-for="(d, i) in uploadInferResult.detections" :key="i" style="margin-right: 8px; margin-bottom: 4px" type="success">
              {{ d.class }} ({{ (d.confidence * 100).toFixed(1) }}%)
            </el-tag>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showInferDialog = false">关闭</el-button>
        <el-button type="primary" @click="runInference" :loading="inferring" v-if="inferTab === 'url'">
          执行推理
        </el-button>
        <el-button type="primary" @click="runUploadInference" :loading="inferring" v-if="inferTab === 'upload'" :disabled="!uploadFile">
          上传并检测
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'

const API_BASE = '/api'

export default {
  name: 'ModelsView',
  components: { UploadFilled },
  setup() {
    const models = ref([])
    const loading = ref(false)
    const deploying = ref(null)
    const inferring = ref(false)
    const showInferDialog = ref(false)
    const selectedModel = ref(null)
    const inferResult = ref(null)
    const inferTab = ref('url')
    const uploadFile = ref(null)
    const annotatedImageUrl = ref('')
    const uploadInferResult = ref(null)
    const uploadRef = ref(null)

    const inferForm = ref({
      imageUrl: '',
      batchMode: false,
    })

    const fetchModels = async () => {
      loading.value = true
      try {
        const res = await fetch(`${API_BASE}/models/`)
        const data = await res.json()
        models.value = data.models || []
      } catch (e) {
        console.error('获取模型列表失败:', e)
      } finally {
        loading.value = false
      }
    }

    const refreshModels = () => {
      fetchModels()
    }

    const deployModel = async (model) => {
      if (model.is_deployed) return
      deploying.value = model.task_id
      try {
        const res = await fetch(`${API_BASE}/models/${model.task_id}/deploy`, { method: 'POST' })
        const data = await res.json()
        if (data.success) {
          ElMessage.success(`模型 ${model.name} 部署成功！`)
          model.is_deployed = true
        } else {
          ElMessage.error(data.message || '部署失败')
        }
      } catch (e) {
        ElMessage.error('部署失败')
      } finally {
        deploying.value = null
      }
    }

    const testInference = (model) => {
      selectedModel.value = model
      inferResult.value = null
      annotatedImageUrl.value = ''
      uploadInferResult.value = null
      uploadFile.value = null
      inferForm.value = { imageUrl: '', batchMode: false }
      inferTab.value = 'url'
      showInferDialog.value = true
    }

    const onUploadChange = (uploadFile) => {
      uploadFile.value = uploadFile.raw
    }

    const runUploadInference = async () => {
      if (!uploadFile.value) {
        ElMessage.warning('请先选择一张图片')
        return
      }
      inferring.value = true
      annotatedImageUrl.value = ''
      uploadInferResult.value = null
      try {
        const formData = new FormData()
        formData.append('file', uploadFile.value)
        const res = await fetch(`${API_BASE}/models/${selectedModel.value.task_id}/infer-image`, {
          method: 'POST',
          body: formData,
        })
        if (res.headers.get('content-type')?.includes('image/jpeg')) {
          const blob = await res.blob()
          annotatedImageUrl.value = URL.createObjectURL(blob)
          uploadInferResult.value = { detections: [] }
          ElMessage.success('检测完成！')
        } else {
          const data = await res.json()
          ElMessage.error(data.message || '推理失败')
        }
      } catch (e) {
        ElMessage.error('上传推理请求失败')
      } finally {
        inferring.value = false
      }
    }

    const runInference = async () => {
      if (!inferForm.value.imageUrl && !inferForm.value.batchMode) {
        ElMessage.warning('请输入图片URL或开启批量测试')
        return
      }
      inferring.value = true
      inferResult.value = null
      try {
        let res
        if (inferForm.value.batchMode) {
          res = await fetch(`${API_BASE}/models/${selectedModel.value.task_id}/batch-infer?max_images=20`, {
            method: 'POST',
          })
        } else {
          res = await fetch(`${API_BASE}/models/${selectedModel.value.task_id}/infer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_urls: [inferForm.value.imageUrl] }),
          })
        }
        const data = await res.json()
        if (data.success) {
          inferResult.value = data
          const times = data.results?.map(r => r.inference_time_ms) || []
          inferResult.value.avg_time_ms = times.length ? times.reduce((a, b) => a + b, 0) / times.length : 0
          ElMessage.success(`推理完成，检测到 ${data.total_detections} 个目标`)
        } else {
          ElMessage.error(data.message || '推理失败')
        }
      } catch (e) {
        ElMessage.error('推理请求失败')
      } finally {
        inferring.value = false
      }
    }

    const downloadModel = (model) => {
      window.open(`${API_BASE}/models/${model.task_id}/download`, '_blank')
    }

    const exportModel = async (model) => {
      try {
        const res = await fetch(`${API_BASE}/models/${model.task_id}/export?format=onnx`)
        const data = await res.json()
        if (data.success) {
          ElMessage.success(`导出成功！格式: ${data.format}, 大小: ${data.file_size}`)
          // 触发下载
          window.open(`${API_BASE}/models/${model.task_id}/export-file?format=onnx`, '_blank')
        } else {
          ElMessage.error(data.message || '导出失败')
        }
      } catch (e) {
        ElMessage.error('导出失败')
      }
    }

    const formatTime = (timeStr) => {
      if (!timeStr) return '-'
      return new Date(timeStr).toLocaleString('zh-CN')
    }

    onMounted(() => {
      fetchModels()
    })

    return {
      models,
      loading,
      deploying,
      inferring,
      showInferDialog,
      selectedModel,
      inferForm,
      inferResult,
      inferTab,
      uploadFile,
      annotatedImageUrl,
      uploadInferResult,
      uploadRef,
      deployModel,
      testInference,
      runInference,
      runUploadInference,
      onUploadChange,
      downloadModel,
      exportModel,
      refreshModels,
      formatTime,
    }
  }
}
</script>

<style scoped>
.models-view {
  padding: 20px;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-good {
  color: #67c23a;
  font-weight: 600;
}

.metric-bad {
  color: #f56c6c;
}

.infer-results {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 15px;
}

.infer-result-card {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 10px;
}

.infer-result-path {
  font-size: 11px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.infer-result-count {
  font-size: 14px;
  margin-top: 5px;
}

.infer-result-time {
  font-size: 12px;
  color: #67c23a;
  margin-top: 3px;
}
</style>
