<template>
  <main class="app-shell" :class="{ expanded: isExpanded }">
    <div class="aurora" aria-hidden="true">
      <span></span>
      <span></span>
      <span></span>
    </div>

    <!-- 初始状态：居中输入卡片 -->
    <div v-if="!isExpanded" class="layout layout-centered">
      <section class="panel panel-form panel-centered">
        <header class="panel-head">
          <div class="logo">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M12 2.5c-.7 0-1.4.2-2 .6L4.6 7C3.6 7.6 3 8.7 3 9.9v4.2c0 1.2.6 2.3 1.6 2.9l5.4 3.9c1.2.8 2.8.8 4 0l5.4-3.9c1-.7 1.6-1.7 1.6-2.9V9.9c0-1.2-.6-2.3-1.6-2.9L14 3.1a3.6 3.6 0 0 0-2-.6Z"
              />
            </svg>
          </div>
          <div>
            <h1>深度研究助手</h1>
            <p>结合多轮智能检索与总结，实时呈现洞见与引用。</p>
          </div>
        </header>

        <ResearchForm
          :loading="isLoading"
          :initial-topic="initialTopic"
          @submit="handleStartResearch"
        />

        <p v-if="error" class="error-chip">
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path
              d="M10 3.2c-.3 0-.6.2-.8.5L3.4 15c-.4.7.1 1.6.8 1.6h11.6c.7 0 1.2-.9.8-1.6L10.8 3.7c-.2-.3-.5-.5-.8-.5Zm0 4.3c.4 0 .7.3.7.7v4c0 .4-.3.7-.7.7s-.7-.3-.7-.7V8.2c0-.4.3-.7.7-.7Zm0 6.6a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z"
            />
          </svg>
          {{ error }}
        </p>
      </section>
    </div>

    <!-- 全屏状态：左右分栏布局 -->
    <div v-else class="layout layout-fullscreen">
      <!-- 左侧：研究信息 -->
      <aside class="sidebar">
        <div class="sidebar-header">
          <button class="back-btn" @click="goBack" :disabled="isLoading">
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            返回
          </button>
          <h2>🔍 深度研究助手</h2>
        </div>

        <div class="research-info">
          <div class="info-item">
            <label>研究主题</label>
            <p class="topic-display">{{ currentTopic }}</p>
          </div>

          <div class="info-item" v-if="tasks.length > 0">
            <label>研究进度</label>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${progressPercentage}%` }"></div>
            </div>
            <p class="progress-text">{{ completedCount }} / {{ tasks.length }} 任务完成</p>
          </div>
        </div>
        
        <!-- Task List Component -->
        <div class="sidebar-tasks" v-if="tasks.length > 0">
           <h3 class="sidebar-subtitle">任务列表</h3>
           <TaskList 
             :tasks="tasks" 
             :active-task-id="activeTaskId"
             @select="selectTask"
           />
        </div>

        <div class="sidebar-actions">
          <div class="upload-section">
            <input 
              type="file" 
              ref="fileInput" 
              style="display: none" 
              accept=".pdf,.txt,.md"
              @change="handleFileUpload"
            >
            <button class="upload-btn" @click="triggerUpload" :disabled="isUploading">
              <svg viewBox="0 0 24 24" width="18" height="18">
                <path d="M12 16L12 4M12 4L8 8M12 4L16 8M4 20H20" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              {{ isUploading ? '上传中...' : '上传知识库文档' }}
            </button>
          </div>
          <button class="new-research-btn" @click="startNewResearch" :disabled="isLoading">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
            </svg>
            开始新研究
          </button>
        </div>
      </aside>

      <!-- 右侧：研究结果 -->
      <section class="panel panel-result">
        <header class="status-bar">
          <div class="status-main">
            <div class="status-chip" :class="{ active: isLoading }">
              <span class="dot"></span>
              {{ isLoading ? "研究进行中" : "研究流程完成" }}
            </div>
            <span class="status-meta">
              {{ activeTask ? `当前任务: ${activeTask.title}` : '等待任务...' }}
            </span>
          </div>
          <div class="status-controls">
            <button class="secondary-btn" @click="logsCollapsed = !logsCollapsed">
              {{ logsCollapsed ? "展开日志" : "收起日志" }}
            </button>
          </div>
        </header>

        <!-- System Logs / Timeline -->
        <div class="timeline-wrapper" v-show="!logsCollapsed && progressLogs.length">
          <ul class="timeline">
            <li v-for="(log, index) in progressLogs" :key="index">
              <span class="timeline-node"></span>
              <p>{{ log }}</p>
            </li>
          </ul>
        </div>

        <!-- Task Details -->
        <div class="task-detail-view" v-if="activeTask">
            <header class="detail-header">
                <h3>{{ activeTask.title }}</h3>
                <span class="status-badge" :class="activeTask.status">{{ formatStatus(activeTask.status) }}</span>
            </header>
            
            <p class="task-intent" v-if="activeTask.intent">{{ activeTask.intent }}</p>
            
            <!-- Task Logs -->
            <div class="detail-section" v-if="activeTask.logs && activeTask.logs.length">
                <h4>执行记录</h4>
                <ul class="detail-logs">
                    <li v-for="(log, idx) in activeTask.logs" :key="idx">{{ log }}</li>
                </ul>
            </div>

            <!-- Sources -->
            <div class="detail-section" v-if="activeTask.sources && activeTask.sources.length">
                <h4>参考来源</h4>
                <ul class="sources-list">
                    <li v-for="(source, idx) in activeTask.sources" :key="idx">
                        <a :href="source" target="_blank" class="source-link">{{ source }}</a>
                    </li>
                </ul>
            </div>

             <!-- Summary -->
            <div class="detail-section" v-if="activeTask.summary">
                <h4>任务总结</h4>
                <div class="markdown-content" v-html="md.render(activeTask.summary)"></div>
            </div>
        </div>
        
        <!-- Final Report -->
        <div v-if="reportMarkdown" class="report-block">
          <h3>最终报告</h3>
          <div class="markdown-content" v-html="md.render(reportMarkdown)"></div>
        </div>
        
        <div v-else-if="!activeTask && !isLoading" class="empty-state">
            <p class="muted">暂无任务信息，请开始研究。</p>
        </div>

      </section>
    </div>
  </main>
</template>

<script lang="ts" setup>
import { ref, computed } from "vue";
import MarkdownIt from "markdown-it";
import ResearchForm from "./components/ResearchForm.vue";
import TaskList from "./components/TaskList.vue";
import { useResearch } from "./composables/useResearch";

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
});

const {
  isLoading,
  error,
  tasks,
  activeTaskId,
  activeTask,
  reportMarkdown,
  progressLogs,
  startResearch,
  resetResearch
} = useResearch();

const isExpanded = ref(false);
const logsCollapsed = ref(false);
const currentTopic = ref("");
const initialTopic = ref("");
const isUploading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

const completedCount = computed(() => tasks.value.filter(t => t.status === 'completed').length);
const progressPercentage = computed(() => {
    if (tasks.value.length === 0) return 0;
    return (completedCount.value / tasks.value.length) * 100;
});

const triggerUpload = () => {
    fileInput.value?.click();
};

const handleFileUpload = async (event: Event) => {
    const target = event.target as HTMLInputElement;
    if (!target.files || target.files.length === 0) return;

    const file = target.files[0];
    const formData = new FormData();
    formData.append("file", file);

    isUploading.value = true;
    try {
        const response = await fetch("http://localhost:8000/upload", {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) throw new Error("Upload failed");
        
        const result = await response.json();
        progressLogs.value.push(`文档上传成功: ${result.filename} (${result.chunks} chunks)`);
    } catch (e: any) {
        error.value = `Upload failed: ${e.message}`;
    } finally {
        isUploading.value = false;
        if (target) target.value = ""; // Reset input
    }
};

const handleStartResearch = async (payload: { topic: string; searchApi: string }) => {
  currentTopic.value = payload.topic;
  isExpanded.value = true;
  await startResearch(payload.topic, payload.searchApi);
};

const selectTask = (id: string) => {
    activeTaskId.value = id;
};

const goBack = () => {
    if (isLoading.value) return;
    isExpanded.value = false;
    // Don't necessarily reset, just hide. But user might want to edit query.
    // If we go back, we probably want to reset or keep the form filled.
    initialTopic.value = currentTopic.value;
    resetResearch();
};

const startNewResearch = () => {
    resetResearch();
    isExpanded.value = false;
    currentTopic.value = "";
    initialTopic.value = "";
};

const formatStatus = (status: string) => {
    const map: Record<string, string> = {
        pending: '待执行',
        in_progress: '执行中',
        completed: '已完成',
        failed: '失败',
    };
    return map[status] || status;
};

</script>

<style scoped>
/* Reuse existing styles */
.app-shell {
  position: relative;
  min-height: 100vh;
  padding: 72px 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at 20% 20%, #f8fafc, #dbeafe 60%);
  color: #1f2937;
  overflow: hidden;
  box-sizing: border-box;
  transition: padding 0.4s ease;
}

.app-shell.expanded {
  padding: 0;
  align-items: stretch;
}

.aurora {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.55;
}

.aurora span {
  position: absolute;
  width: 45vw;
  height: 45vw;
  max-width: 520px;
  max-height: 520px;
  background: radial-gradient(circle, rgba(148, 197, 255, 0.35), transparent 60%);
  filter: blur(90px);
  animation: float 26s infinite linear;
}

.aurora span:nth-child(1) { top: -20%; left: -18%; animation-delay: 0s; }
.aurora span:nth-child(2) { bottom: -25%; right: -20%; background: radial-gradient(circle, rgba(166, 139, 255, 0.28), transparent 60%); animation-delay: -9s; }
.aurora span:nth-child(3) { top: 35%; left: 45%; background: radial-gradient(circle, rgba(164, 219, 216, 0.26), transparent 60%); animation-delay: -16s; }

.layout {
  position: relative;
  width: 100%;
  display: flex;
  gap: 24px;
  z-index: 1;
  transition: all 0.4s ease;
}

.layout-centered {
  max-width: 600px;
  justify-content: center;
  align-items: center;
}

.layout-fullscreen {
  height: 100vh;
  max-width: 100%;
  gap: 0;
  align-items: stretch;
}

.panel {
  position: relative;
  flex: 1 1 360px;
  padding: 24px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.12);
  backdrop-filter: blur(8px);
  overflow: hidden;
}

.panel-form { max-width: 420px; }
.panel-centered { width: 100%; max-width: 600px; padding: 40px; box-shadow: 0 32px 64px rgba(15, 23, 42, 0.15); transform: scale(1); transition: transform 0.3s ease, box-shadow 0.3s ease; }
.panel-centered:hover { transform: scale(1.02); box-shadow: 0 40px 80px rgba(15, 23, 42, 0.2); }
.panel-result { min-width: 360px; flex: 2 1 420px; display: flex; flex-direction: column; gap: 18px; overflow-y: auto; }

.panel-head { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.logo { width: 52px; height: 52px; display: grid; place-items: center; border-radius: 16px; background: linear-gradient(135deg, #2563eb, #7c3aed); box-shadow: 0 12px 28px rgba(59, 130, 246, 0.4); }
.logo svg { width: 28px; height: 28px; fill: #f8fafc; }
.panel-form h1 { margin: 0; font-size: 26px; letter-spacing: 0.01em; }
.panel-form p { margin: 4px 0 0; color: #64748b; font-size: 13px; }

.error-chip { margin-top: 16px; display: inline-flex; align-items: center; gap: 8px; padding: 10px 14px; background: rgba(248, 113, 113, 0.12); border: 1px solid rgba(248, 113, 113, 0.35); border-radius: 14px; color: #b91c1c; font-size: 14px; }
.error-chip svg { width: 18px; height: 18px; fill: currentColor; }

/* Sidebar */
.sidebar { width: 340px; min-width: 340px; height: 100vh; background: rgba(255, 255, 255, 0.98); border-right: 1px solid rgba(148, 163, 184, 0.2); padding: 32px 24px; display: flex; flex-direction: column; gap: 24px; overflow-y: auto; box-shadow: 4px 0 24px rgba(15, 23, 42, 0.08); }
.sidebar-header { display: flex; flex-direction: column; gap: 16px; }
.sidebar-header h2 { font-size: 20px; font-weight: 700; margin: 0; color: #1f2937; }
.back-btn { display: flex; align-items: center; gap: 8px; padding: 10px 16px; background: transparent; border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 12px; color: #64748b; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.2s ease; width: fit-content; }
.back-btn:hover:not(:disabled) { background: rgba(59, 130, 246, 0.1); border-color: #3b82f6; color: #3b82f6; }
.back-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.research-info { display: flex; flex-direction: column; gap: 20px; }
.info-item { display: flex; flex-direction: column; gap: 8px; }
.info-item label { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; }
.topic-display { font-size: 15px !important; font-weight: 600; color: #0f172a !important; padding: 12px; background: rgba(59, 130, 246, 0.05); border-radius: 8px; border-left: 3px solid #3b82f6; margin: 0; }
.progress-bar { width: 100%; height: 8px; background: rgba(148, 163, 184, 0.2); border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); border-radius: 4px; transition: width 0.5s ease; }
.progress-text { font-size: 13px !important; color: #64748b !important; font-weight: 500; margin: 4px 0 0; }

.sidebar-tasks { flex: 1; display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.sidebar-subtitle { font-size: 14px; font-weight: 600; color: #475569; margin: 0; text-transform: uppercase; letter-spacing: 0.5px; }

.sidebar-actions { margin-top: auto; padding-top: 16px; border-top: 1px solid rgba(148, 163, 184, 0.2); display: flex; flex-direction: column; gap: 10px; }
.new-research-btn { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 14px 20px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); border: none; border-radius: 12px; color: white; font-size: 15px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3); width: 100%; }
.new-research-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4); }
.new-research-btn:disabled { opacity: 0.7; cursor: not-allowed; transform: none; }

.upload-btn { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 20px; background: transparent; border: 1px dashed #94a3b8; border-radius: 12px; color: #64748b; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.3s ease; width: 100%; }
.upload-btn:hover:not(:disabled) { background: rgba(241, 245, 249, 0.6); border-color: #3b82f6; color: #3b82f6; }


/* Result Panel */
.status-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding-bottom: 12px; border-bottom: 1px solid rgba(226, 232, 240, 0.6); }
.status-main { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.status-chip { display: inline-flex; align-items: center; gap: 8px; background: rgba(191, 219, 254, 0.28); padding: 6px 12px; border-radius: 999px; font-size: 13px; color: #1f2937; border: 1px solid rgba(59, 130, 246, 0.35); transition: background 0.3s ease; }
.status-chip.active { background: rgba(129, 140, 248, 0.2); border-color: rgba(129, 140, 248, 0.4); color: #1e293b; }
.status-chip .dot { width: 8px; height: 8px; border-radius: 999px; background: #2563eb; box-shadow: 0 0 12px rgba(37, 99, 235, 0.45); animation: pulse 1.8s ease-in-out infinite; }
.status-meta { color: #64748b; font-size: 13px; font-weight: 500; }
.secondary-btn { padding: 6px 12px; border-radius: 8px; background: white; border: 1px solid #cbd5e1; color: #475569; font-size: 12px; cursor: pointer; }

.timeline-wrapper { max-height: 180px; overflow-y: auto; padding: 12px; background: rgba(241, 245, 249, 0.5); border-radius: 12px; border: 1px solid rgba(226, 232, 240, 0.8); }
.timeline { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; position: relative; padding-left: 12px; }
.timeline::before { content: ""; position: absolute; top: 6px; bottom: 6px; left: 0; width: 2px; background: #cbd5e1; }
.timeline li { position: relative; padding-left: 16px; color: #475569; font-size: 13px; line-height: 1.4; }
.timeline-node { position: absolute; left: -5px; top: 5px; width: 8px; height: 8px; border-radius: 50%; background: #94a3b8; border: 2px solid #fff; }

.task-detail-view { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border: 1px solid #e2e8f0; display: flex; flex-direction: column; gap: 20px; }
.detail-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding-bottom: 16px; }
.detail-header h3 { margin: 0; font-size: 18px; color: #1e293b; }
.status-badge { font-size: 12px; padding: 4px 10px; border-radius: 999px; font-weight: 600; }
.status-badge.pending { background: #f1f5f9; color: #64748b; }
.status-badge.in_progress { background: #dbeafe; color: #2563eb; }
.status-badge.completed { background: #dcfce7; color: #166534; }
.status-badge.failed { background: #fee2e2; color: #991b1b; }

.task-intent { color: #64748b; font-size: 14px; margin: 0; background: #f8fafc; padding: 12px; border-radius: 8px; border-left: 3px solid #cbd5e1; }

.detail-section h4 { margin: 0 0 10px; font-size: 14px; font-weight: 600; color: #334155; text-transform: uppercase; letter-spacing: 0.05em; }
.detail-logs { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.detail-logs li { font-size: 13px; color: #475569; padding: 4px 8px; background: #f8fafc; border-radius: 4px; border: 1px solid #f1f5f9; font-family: monospace; }

.sources-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.source-link { color: #2563eb; text-decoration: none; font-size: 13px; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.source-link:hover { text-decoration: underline; }

.report-block { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); border: 1px solid #e2e8f0; }
.report-block h3 { margin: 0 0 16px; font-size: 20px; color: #1e293b; }

.markdown-content { font-size: 15px; line-height: 1.7; color: #334155; }
.markdown-content :deep(h1), .markdown-content :deep(h2), .markdown-content :deep(h3) { color: #1e293b; margin-top: 1.5em; margin-bottom: 0.8em; font-weight: 700; }
.markdown-content :deep(p) { margin-bottom: 1em; }
.markdown-content :deep(ul), .markdown-content :deep(ol) { padding-left: 1.5em; margin-bottom: 1em; }
.markdown-content :deep(pre) { background: #f1f5f9; padding: 16px; border-radius: 8px; overflow-x: auto; font-family: monospace; font-size: 13px; }

@keyframes float { 0% { transform: translate3d(0, 0, 0) rotate(0deg); } 50% { transform: translate3d(10%, 6%, 0) rotate(3deg); } 100% { transform: translate3d(0, 0, 0) rotate(0deg); } }
@keyframes pulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.3); opacity: 0.5; } }
</style>
