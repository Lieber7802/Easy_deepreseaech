<script setup lang="ts">
import { computed } from 'vue';
import type { Task } from '../composables/useResearch';

const props = defineProps<{
  tasks: Task[];
  activeTaskId: string | null;
}>();

const emit = defineEmits<{
  (e: 'select', id: string): void;
}>();

const formatTaskStatus = (status: string) => {
  const map: Record<string, string> = {
    pending: '待执行',
    in_progress: '执行中',
    completed: '已完成',
    failed: '失败',
  };
  return map[status] || status;
};
</script>

<template>
  <div class="task-list">
    <div
      v-for="task in tasks"
      :key="task.id"
      class="task-item"
      :class="{
        active: task.id === activeTaskId,
        pending: task.status === 'pending',
        in_progress: task.status === 'in_progress',
        completed: task.status === 'completed',
        failed: task.status === 'failed'
      }"
      @click="emit('select', task.id)"
    >
      <div class="task-header">
        <div class="task-title-group">
          <!-- Spinner for in_progress -->
          <div v-if="task.status === 'in_progress'" class="mini-spinner"></div>
          <!-- Status Icon for completed/failed -->
          <div v-else-if="task.status === 'completed'" class="status-icon success">✓</div>
          <div v-else-if="task.status === 'failed'" class="status-icon error">✕</div>
          <div v-else class="status-icon pending">●</div>
          
          <span class="task-title" :title="task.title">{{ task.title }}</span>
        </div>
        <span class="status-badge" :class="task.status">
          {{ formatTaskStatus(task.status) }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}

.task-item:hover {
  border-color: #cbd5e1;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.task-item.active {
  border-color: #3b82f6;
  background-color: #eff6ff;
  box-shadow: 0 0 0 1px #3b82f6;
}

/* Status Styles */
.task-item.in_progress {
  border-color: #93c5fd;
  background: linear-gradient(90deg, #eff6ff, #dbeafe);
}

/* Scanning animation for in_progress */
.task-item.in_progress::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, #3b82f6, transparent);
  width: 50%;
  animation: scanning 2s ease-in-out infinite;
}

@keyframes scanning {
  0% { left: -50%; }
  100% { left: 100%; }
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.task-title-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.task-title {
  font-weight: 500;
  color: #1e293b;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 500;
  white-space: nowrap;
}

.status-badge.pending { background: #f1f5f9; color: #64748b; }
.status-badge.in_progress { background: #dbeafe; color: #2563eb; }
.status-badge.completed { background: #dcfce7; color: #166534; }
.status-badge.failed { background: #fee2e2; color: #991b1b; }

/* Icons */
.mini-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(37, 99, 235, 0.2);
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-icon {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-icon.success { background: #22c55e; color: white; }
.status-icon.error { background: #ef4444; color: white; }
.status-icon.pending { background: #cbd5e1; color: white; }
</style>
