<template>
  <span class="status-badge" :class="`status-badge--${status}`">
    <span class="dot" v-if="showDot"></span>
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, required: true },
  showDot: { type: Boolean, default: true },
})

const labelMap = {
  pending: '待处理',
  data_processing: '数据处理',
  training: '训练中',
  completed: '已完成',
  failed: '失败',
  running: '运行中',
  stopped: '已停止',
  deploying: '部署中',
  deployed: '已部署',
}

const label = computed(() => labelMap[props.status] || props.status)
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-badge--pending {
  background: var(--color-surface-2);
  color: var(--color-text-muted);
}

.status-badge--data_processing,
.status-badge--deploying {
  background: var(--color-accent-bg);
  color: var(--color-accent);
}

.status-badge--training,
.status-badge--running {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.status-badge--completed,
.status-badge--deployed {
  background: var(--color-secondary-bg);
  color: var(--color-secondary);
}

.status-badge--failed,
.status-badge--stopped {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
</style>
