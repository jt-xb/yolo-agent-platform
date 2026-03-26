<template>
  <div class="empty-state">
    <div class="empty-icon">{{ icon }}</div>
    <div class="empty-title">{{ title }}</div>
    <div class="empty-desc" v-if="description">{{ description }}</div>
    <slot></slot>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: '📦' },
  title: { type: String, default: '暂无数据' },
  description: { type: String, default: '' },
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-12) var(--space-6);
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: var(--space-4);
  opacity: 0.6;
}

.empty-title {
  font-size: var(--text-md);
  font-weight: var(--font-medium);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.empty-desc {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  max-width: 320px;
}
</style>
