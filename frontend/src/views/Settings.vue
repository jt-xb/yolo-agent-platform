<template>
  <div class="settings-view">
    <h2>系统设置</h2>

    <!-- 系统状态 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <span>📊 系统状态</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="服务状态">
          <el-tag type="success">在线</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="版本">{{ systemStatus.version }}</el-descriptions-item>
        <el-descriptions-item label="LLM 模型">{{ systemStatus.llm_model }}</el-descriptions-item>
        <el-descriptions-item label="LLM 状态">
          <el-tag :type="systemStatus.llm_status === 'ready' ? 'success' : 'warning'">
            {{ systemStatus.llm_status === 'ready' ? '就绪' : '未就绪' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="GPU">
          {{ systemStatus.gpu_name }}
        </el-descriptions-item>
        <el-descriptions-item label="GPU 显存">
          {{ systemStatus.gpu_memory_used }} / {{ systemStatus.gpu_memory_total }} MB
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 算力资源 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <span>🖥️ 算力资源监控</span>
      </template>
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="resource-item">
            <span class="label">CPU 使用率</span>
            <el-progress :percentage="systemMetrics.cpu_percent" type="circle" />
          </div>
        </el-col>
        <el-col :span="6">
          <div class="resource-item">
            <span class="label">内存使用率</span>
            <el-progress :percentage="systemMetrics.memory_percent" type="circle" />
          </div>
        </el-col>
        <el-col :span="6">
          <div class="resource-item">
            <span class="label">GPU 使用率</span>
            <el-progress :percentage="systemMetrics.gpu_percent" type="circle" color="#67C23A" />
          </div>
        </el-col>
        <el-col :span="6">
          <div class="resource-item">
            <span class="label">磁盘使用率</span>
            <el-progress :percentage="systemMetrics.disk_percent" type="circle" color="#E6A23C" />
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- MLU 设置 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <span>⚙️ MLU370 配置</span>
      </template>
      <el-form label-width="120px">
        <el-form-item label="启用 MLU">
          <el-switch v-model="mluSettings.enabled" disabled />
          <span style="margin-left: 10px; color: #909399; font-size: 12px;">
            (当前环境为模拟配置)
          </span>
        </el-form-item>
        <el-form-item label="设备 ID">
          <el-input v-model="mluSettings.device_id" disabled />
        </el-form-item>
        <el-form-item label="默认模型">
          <el-select v-model="mluSettings.default_model" disabled>
            <el-option label="YOLOv8 Nano" value="yolov8n" />
            <el-option label="YOLOv8 Small" value="yolov8s" />
            <el-option label="YOLOv8 Medium" value="yolov8m" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- LLM 配置 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <span>🤖 LLM 配置</span>
      </template>
      <el-form label-width="120px">
        <el-form-item label="模型名称">
          <el-input v-model="llmConfig.model" placeholder="deepseek-v3.2" disabled />
        </el-form-item>
        <el-form-item label="API 地址">
          <el-input v-model="llmConfig.api_base" placeholder="http://localhost:8000/v1" disabled />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="llmConfig.api_key" type="password" disabled show-password />
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'

const API_BASE = '/api'

export default {
  name: 'SettingsView',
  setup() {
    const systemStatus = ref({
      status: 'online',
      version: '0.1.0',
      gpu_name: 'MLU370',
      gpu_memory_total: 16384,
      gpu_memory_used: 4096,
      llm_model: 'deepseek-v3.2',
      llm_status: 'ready',
    })

    const systemMetrics = ref({
      cpu_percent: 45.2,
      memory_percent: 62.8,
      gpu_percent: 78.5,
      disk_percent: 33.1,
    })

    const mluSettings = ref({
      enabled: false,  // TODO: 根据实际环境
      device_id: '0',
      default_model: 'yolov8n',
    })

    const llmConfig = ref({
      model: 'deepseek-v3.2',
      api_base: 'http://localhost:8000/v1',
      api_key: '********',
    })

    let refreshInterval = null

    const fetchSystemStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/system/status`)
        if (res.ok) {
          systemStatus.value = await res.json()
        }
      } catch (e) {
        console.error('获取系统状态失败:', e)
      }
    }

    const fetchSystemMetrics = async () => {
      try {
        const res = await fetch(`${API_BASE}/system/metrics`)
        if (res.ok) {
          systemMetrics.value = await res.json()
        }
      } catch (e) {
        console.error('获取系统指标失败:', e)
      }
    }

    onMounted(() => {
      fetchSystemStatus()
      fetchSystemMetrics()
      // 每10秒刷新一次
      refreshInterval = setInterval(() => {
        fetchSystemMetrics()
      }, 10000)
    })

    onUnmounted(() => {
      if (refreshInterval) clearInterval(refreshInterval)
    })

    return {
      systemStatus,
      systemMetrics,
      mluSettings,
      llmConfig,
    }
  }
}
</script>

<style scoped>
.settings-view {
  padding: 20px;
}

.settings-view h2 {
  font-size: 20px;
  font-weight: 500;
}

.resource-item {
  text-align: center;
}

.resource-item .label {
  display: block;
  margin-bottom: 10px;
  color: #606266;
}
</style>
