<template>
  <div id="app">
    <el-container>
      <!-- 顶部导航 -->
      <el-header class="header">
        <div class="header-left">
          <div class="logo-area">
            <span class="logo-icon">🤖</span>
            <div class="logo-text">
              <h1>YOLO Agent 平台</h1>
              <span class="logo-subtitle">AI 驱动的自动化目标检测训练</span>
            </div>
          </div>
        </div>
        <div class="header-center">
          <!-- Agent 状态概览 -->
          <div class="agent-status-bar" v-if="agentStats">
            <div class="agent-stat">
              <span class="stat-icon">🎯</span>
              <span class="stat-value">{{ agentStats.total_tasks }}</span>
              <span class="stat-label">训练任务</span>
            </div>
            <div class="agent-stat" :class="{ active: agentStats.training_count > 0 }">
              <span class="stat-icon">⚡</span>
              <span class="stat-value">{{ agentStats.training_count }}</span>
              <span class="stat-label">Agent 训练中</span>
            </div>
            <div class="agent-stat completed">
              <span class="stat-icon">✅</span>
              <span class="stat-value">{{ agentStats.completed_count }}</span>
              <span class="stat-label">已完成</span>
            </div>
            <div class="agent-stat" v-if="agentStats.current_action">
              <span class="stat-icon spinning">🔄</span>
              <span class="stat-value current-action">{{ agentStats.current_action }}</span>
              <span class="stat-label">Agent 正在</span>
            </div>
          </div>
        </div>
        <div class="header-right">
          <el-button @click="refreshStatus" :loading="loading" size="small">
            🔄 刷新
          </el-button>
        </div>
      </el-header>

      <el-container>
        <!-- 侧边栏 -->
        <el-aside width="220px" class="sidebar">
          <div class="sidebar-header">
            <span class="sidebar-title">导航菜单</span>
          </div>
          <el-menu :default-active="activeMenu" router class="sidebar-menu">
            <el-menu-item index="/">
              <template #title>
                <span class="menu-icon">📋</span>
                <span>任务管理</span>
                <span class="menu-badge" v-if="agentStats?.training_count > 0">{{ agentStats.training_count }}</span>
              </template>
            </el-menu-item>
            <el-menu-item index="/datasets">
              <template #title>
                <span class="menu-icon">📁</span>
                <span>数据管理</span>
              </template>
            </el-menu-item>
            <el-menu-item index="/models">
              <template #title>
                <span class="menu-icon">🤖</span>
                <span>模型仓库</span>
              </template>
            </el-menu-item>
            <el-menu-item index="/settings">
              <template #title>
                <span class="menu-icon">⚙️</span>
                <span>系统设置</span>
              </template>
            </el-menu-item>
          </el-menu>

          <!-- Agent 说明卡片 -->
          <div class="agent-info-card">
            <div class="agent-info-header">
              <span class="agent-avatar">🤖</span>
              <span class="agent-name">Agent</span>
            </div>
            <p class="agent-desc">
              平台内置 AI Agent，自动分析训练效果、智能调整参数、迭代优化模型，全程无需人工干预。
            </p>
            <div class="agent-features">
              <div class="feature-item">🧠 智能参数调优</div>
              <div class="feature-item">🔄 自动迭代优化</div>
              <div class="feature-item">📊 实时效果评估</div>
            </div>
          </div>
        </el-aside>

        <!-- 主内容区 -->
        <el-main class="main-content">
          <router-view @agent-update="onAgentUpdate" />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

export default {
  name: 'App',
  setup() {
    const router = useRouter()
    const activeMenu = ref('/')
    const loading = ref(false)
    const agentStats = ref({
      total_tasks: 0,
      training_count: 0,
      completed_count: 0,
      current_action: ''
    })

    let pollInterval = null

    const refreshStatus = async () => {
      loading.value = true
      try {
        const res = await fetch('/api/tasks/')
        if (res.ok) {
          const data = await res.json()
          const tasks = data.tasks || []
          agentStats.value = {
            total_tasks: tasks.length,
            training_count: tasks.filter(t => t.status === 'training').length,
            completed_count: tasks.filter(t => t.status === 'completed').length,
            current_action: tasks.find(t => t.status === 'training')?.name || ''
          }
        }
      } catch (e) {
        // 后端未启动时静默处理
      } finally {
        loading.value = false
      }
    }

    const onAgentUpdate = (stats) => {
      agentStats.value = { ...agentStats.value, ...stats }
    }

    onMounted(() => {
      activeMenu.value = router.currentRoute.value.path
      refreshStatus()
      // 每 5 秒刷新一次状态
      pollInterval = setInterval(refreshStatus, 5000)
    })

    onUnmounted(() => {
      if (pollInterval) clearInterval(pollInterval)
    })

    return {
      activeMenu,
      loading,
      agentStats,
      refreshStatus,
      onAgentUpdate,
    }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Helvetica Neue', Arial, sans-serif;
  background: #f0f2f5;
}

#app {
  height: 100vh;
}

.header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 64px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.header-left {
  display: flex;
  align-items: center;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 32px;
}

.logo-text h1 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  line-height: 1.2;
}

.logo-subtitle {
  font-size: 11px;
  color: #a0aec0;
  display: block;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.agent-status-bar {
  display: flex;
  gap: 24px;
  background: rgba(255,255,255,0.08);
  padding: 8px 20px;
  border-radius: 24px;
  border: 1px solid rgba(255,255,255,0.1);
}

.agent-stat {
  display: flex;
  align-items: center;
  gap: 6px;
  opacity: 0.7;
  transition: opacity 0.3s;
}

.agent-stat.active {
  opacity: 1;
}

.agent-stat.completed .stat-icon {
  color: #67c23a;
}

.stat-icon {
  font-size: 16px;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
}

.stat-label {
  font-size: 11px;
  color: #a0aec0;
}

.current-action {
  font-size: 12px;
  color: #409eff;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.spinning {
  animation: spin 1s linear infinite;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sidebar {
  background: white;
  border-right: 1px solid #e6e6e6;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.sidebar-header {
  padding: 16px 20px 8px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.sidebar-title {
  font-size: 11px;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.sidebar-menu {
  border-right: none;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.sidebar-menu .el-menu-item {
  height: 48px;
  line-height: 48px;
}

.menu-icon {
  font-size: 18px;
  margin-right: 10px;
}

.menu-badge {
  background: #f56c6c;
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  margin-left: auto;
}

.agent-info-card {
  margin: 16px;
  margin-top: auto;
  padding: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
  flex-shrink: 0;
}

.agent-info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.agent-avatar {
  font-size: 24px;
}

.agent-name {
  font-weight: 600;
  font-size: 16px;
}

.agent-desc {
  font-size: 12px;
  line-height: 1.6;
  opacity: 0.9;
  margin-bottom: 12px;
}

.agent-features {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.feature-item {
  font-size: 12px;
  opacity: 0.85;
}

.main-content {
  padding: 0;
  background: #f0f2f5;
  overflow-y: auto;
}
</style>
