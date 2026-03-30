<template>
  <div class="settings-view">
    <div class="page-header">
      <h2 class="section-title">系统设置</h2>
    </div>

    <div class="settings-content">
      <!-- LLM Configuration -->
      <div class="settings-card">
        <h3 class="card-title">🤖 LLM 配置</h3>
        <p class="card-desc">配置大模型 API，用于 Agent 训练时的智能决策。离线模式下可留空，将使用规则引擎。</p>

        <el-form label-position="top" style="max-width: 560px; margin-top: 20px">
          <el-form-item label="API 地址">
            <el-input
              v-model="llmForm.api_base"
              placeholder="https://api.deepseek.com/v1"
              clearable
            />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input
              v-model="llmForm.api_key"
              type="password"
              placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              show-password
              clearable
            />
          </el-form-item>
          <el-form-item label="模型">
            <el-select v-model="llmForm.model" style="width: 100%">
              <el-option label="DeepSeek V3 (deepseek-chat)" value="deepseek-chat" />
              <el-option label="DeepSeek Coder (deepseek-coder)" value="deepseek-coder" />
              <el-option label="GPT-4o" value="gpt-4o" />
              <el-option label="GPT-4o-mini" value="gpt-4o-mini" />
              <el-option label="自定义" value="custom" />
            </el-select>
          </el-form-item>
          <el-form-item label="启用 LLM">
            <el-switch v-model="llmForm.enabled" />
            <span style="margin-left: 12px; font-size: 12px; color: var(--color-text-muted)">
              关闭后训练将使用规则引擎，不调用 LLM
            </span>
          </el-form-item>
        </el-form>

        <div class="card-actions">
          <el-button @click="testConnection" :loading="testing" :disabled="!llmForm.api_key">
            测试连接
          </el-button>
          <el-button type="primary" @click="saveConfig" :loading="saving">
            保存配置
          </el-button>
        </div>

        <el-alert
          v-if="testResult"
          :type="testResult.success ? 'success' : 'error'"
          :closable="false"
          style="margin-top: 16px"
        >
          {{ testResult.message }}
        </el-alert>
      </div>

      <!-- MLU370 Configuration -->
      <div class="settings-card">
        <h3 class="card-title">🖥️ MLU370 加速配置</h3>
        <p class="card-desc">配置寒武纪 MLU370 加速卡进行训练加速。需要安装寒武纪 Pytorch SDK。</p>

        <el-form label-position="top" style="max-width: 400px; margin-top: 20px">
          <el-form-item label="启用 MLU370">
            <el-switch v-model="mluForm.enabled" />
          </el-form-item>
          <el-form-item label="设备 ID">
            <el-input-number v-model="mluForm.device_id" :min="0" :max="7" style="width: 100%" />
          </el-form-item>
        </el-form>

        <div class="card-actions">
          <el-button type="primary" @click="saveMluConfig" :loading="savingMlu">
            保存配置
          </el-button>
        </div>
      </div>

      <!-- About -->
      <div class="settings-card">
        <h3 class="card-title">ℹ️ 关于</h3>
        <div class="about-info">
          <p><strong>YOLO Agent Platform</strong></p>
          <p>基于大模型 Agent 的 YOLO 自动化训推一体化 Web 平台</p>
          <p style="margin-top: 8px; color: var(--color-text-muted); font-size: 12px">
            版本 1.0.0 | 支持 YOLOv8 系列模型
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getLlmConfig, saveLlmConfig, testLlmConnection } from '../api/settings'

const llmForm = ref({
  api_base: '',
  api_key: '',
  model: 'deepseek-chat',
  enabled: true,
})

const mluForm = ref({
  enabled: false,
  device_id: 0,
})

const testing = ref(false)
const saving = ref(false)
const savingMlu = ref(false)
const testResult = ref(null)

async function loadConfig() {
  try {
    const data = await getLlmConfig()
    llmForm.value = {
      api_base: data.api_base || '',
      api_key: data.api_key || '',
      model: data.model || 'deepseek-chat',
      enabled: data.enabled !== false,
    }
  } catch (e) {
    console.error('loadConfig error:', e)
  }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const data = await testLlmConnection(llmForm.value)
    testResult.value = data
  } catch (e) {
    testResult.value = { success: false, message: '连接失败: ' + e.message }
  } finally {
    testing.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    await saveLlmConfig(llmForm.value)
    ElMessage.success('LLM 配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

async function saveMluConfig() {
  savingMlu.value = true
  try {
    // TODO: implement MLU config save API
    ElMessage.success('MLU 配置已保存（需重启后端生效）')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    savingMlu.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.settings-view {
  max-width: 800px;
}

.page-header {
  margin-bottom: var(--space-5);
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.settings-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-5);
}

.card-title {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  margin-bottom: var(--space-2);
}

.card-desc {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  margin-bottom: 0;
}

.card-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.about-info {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-top: var(--space-3);
}
</style>
