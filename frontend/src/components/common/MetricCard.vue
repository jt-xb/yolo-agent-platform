<template>
  <div class="metric-card" :class="`metric-card--${variant}`">
    <div class="metric-icon" v-if="icon">{{ icon }}</div>
    <div class="metric-body">
      <div class="metric-value">{{ value }}</div>
      <div class="metric-label">{{ label }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  value: { type: [String, Number], required: true },
  label: { type: String, required: true },
  icon: { type: String, default: '' },
  variant: { type: String, default: 'default' }, // default | success | warning | danger
})
</script>

<style scoped>
.metric-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--color-border);
}

.metric-icon {
  font-size: var(--text-xl);
}

.metric-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-value {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--color-text);
  line-height: 1;
}

.metric-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.metric-card--success .metric-value { color: var(--color-secondary); }
.metric-card--warning .metric-value { color: var(--color-accent); }
.metric-card--danger .metric-value { color: var(--color-danger); }
</style>
