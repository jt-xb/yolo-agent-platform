<template>
  <el-container class="app-layout">
    <!-- Sidebar -->
    <el-aside class="sidebar" :width="collapsed ? '64px' : '220px'">
      <div class="sidebar-logo">
        <span class="logo-icon">AI</span>
        <span v-show="!collapsed" class="logo-text">YOLO Agent</span>
      </div>

      <el-menu
        :default-active="route.path"
        class="sidebar-menu"
        :collapse="collapsed"
        router
      >
        <el-menu-item index="/tasks">
          <span class="menu-icon">T</span>
          <template #title>训练任务</template>
        </el-menu-item>
        <el-menu-item index="/agent">
          <span class="menu-icon">A</span>
          <template #title>🤖 Agent训练</template>
        </el-menu-item>
        <el-menu-item index="/datasets">
          <span class="menu-icon">D</span>
          <template #title>数据集</template>
        </el-menu-item>
        <el-menu-item index="/models">
          <span class="menu-icon">M</span>
          <template #title>模型中心</template>
        </el-menu-item>
        <el-menu-item index="/settings">
          <span class="menu-icon">S</span>
          <template #title>系统设置</template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <el-button text @click="collapsed = !collapsed" class="collapse-btn">
          {{ collapsed ? '→' : '←' }}
        </el-button>
      </div>
    </el-aside>

    <!-- Main -->
    <el-container class="main-container">
      <el-header class="header">
        <div class="header-left">
          <h1 class="page-title">{{ pageTitle }}</h1>
        </div>
        <div class="header-right">
          <div class="agent-status">
            <span class="status-dot"></span>
            <span class="status-text">Agent Ready</span>
          </div>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const collapsed = ref(false)

const pageTitleMap = {
  '/tasks': '训练任务中心',
  '/agent': 'Agent 智能训练',
  '/datasets': '数据集管理',
  '/models': '模型中心',
  '/settings': '系统设置',
}

const pageTitle = computed(() => pageTitleMap[route.path] || 'YOLO Agent')
</script>

<style>
.app-layout {
  min-height: 100vh;
}

/* Sidebar */
.sidebar {
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-base);
  overflow: hidden;
}

.sidebar-logo {
  height: var(--header-height);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-4);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.logo-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark));
  color: white;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--font-bold);
  font-size: var(--text-sm);
  flex-shrink: 0;
}

.logo-text {
  font-weight: var(--font-semibold);
  font-size: var(--text-md);
  color: var(--color-text);
  white-space: nowrap;
}

.sidebar-menu {
  flex: 1;
  border: none;
  padding: var(--space-2) 0;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 220px;
}

.el-menu-item {
  height: 44px;
  line-height: 44px;
  margin: 2px var(--space-2);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
}

.el-menu-item:hover {
  background: var(--color-surface-2);
  color: var(--color-text);
}

.el-menu-item.is-active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.el-menu-item.is-active .menu-icon {
  background: var(--color-primary);
  color: white;
}

.menu-icon {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--color-surface-2);
  color: var(--color-text-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: var(--font-bold);
  margin-right: var(--space-3);
}

.sidebar-footer {
  padding: var(--space-3);
  border-top: 1px solid var(--color-border);
  display: flex;
  justify-content: flex-end;
}

.collapse-btn {
  color: var(--color-text-muted);
}

/* Main */
.main-container {
  flex-direction: column;
}

.header {
  height: var(--header-height);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
}

.page-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}

.agent-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-secondary-bg);
  border-radius: var(--radius-full);
}

.status-dot {
  width: 8px;
  height: 8px;
  background: var(--color-secondary);
  border-radius: 50%;
  animation: pulse 2s infinite;
}

.status-text {
  font-size: var(--text-sm);
  color: var(--color-secondary);
  font-weight: var(--font-medium);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.main-content {
  padding: var(--space-6);
  background: var(--color-bg);
  overflow-y: auto;
}
</style>
