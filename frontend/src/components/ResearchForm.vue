<template>
  <form class="form" @submit.prevent="handleSubmit">
    <label class="field">
      <span>研究主题</span>
      <textarea
        v-model="form.topic"
        placeholder="例如：探索多模态模型在 2025 年的关键突破"
        rows="4"
        required
        :disabled="loading"
      ></textarea>
    </label>

    <section class="options">
      <label class="field option">
        <span>搜索引擎</span>
        <select v-model="form.searchApi" :disabled="loading">
          <option value="">沿用后端配置</option>
          <option v-for="option in searchOptions" :key="option" :value="option">
            {{ option }}
          </option>
        </select>
      </label>
      
      <label class="field option">
        <span>上传知识库文档 (RAG)</span>
        <div class="upload-wrapper">
             <input 
              type="file" 
              ref="fileInput" 
              class="file-input"
              accept=".pdf,.txt,.md"
              @change="handleFileUpload"
              :disabled="isUploading || loading"
            >
             <div class="upload-trigger" @click="triggerUpload" :class="{ disabled: isUploading || loading }">
                <svg viewBox="0 0 24 24" width="18" height="18">
                    <path d="M12 16L12 4M12 4L8 8M12 4L16 8M4 20H20" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>{{ isUploading ? '上传中...' : (uploadStatus || '点击选择文件') }}</span>
             </div>
        </div>
      </label>
    </section>

    <!-- Skills Management Section -->
    <section class="skills-section">
      <div class="skills-header" @click="toggleSkills" :class="{ expanded: showSkills }">
        <span class="title">技能管理 (Skills & MCP)</span>
        <span class="subtitle">{{ availableSkills.length }} 个可用</span>
        <svg class="arrow" viewBox="0 0 24 24" width="16" height="16">
          <path d="M6 9L12 15L18 9" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      
      <div class="skills-list" v-if="showSkills">
        <div v-for="skill in availableSkills" :key="skill.name" class="skill-item">
          <div class="skill-info">
            <span class="skill-name">{{ skill.name }}</span>
            <span class="skill-desc">{{ skill.description }}</span>
          </div>
          <label class="switch">
            <input type="checkbox" :checked="true" @change="toggleSkill(skill.name, $event)">
            <span class="slider round"></span>
          </label>
        </div>
        <div v-if="availableSkills.length === 0" class="no-skills">
          加载技能中...
        </div>
      </div>
    </section>

    <div class="form-actions">
      <button class="submit" type="submit" :disabled="loading || !form.topic.trim()">
        <span class="submit-label">
          <svg
            v-if="loading"
            class="spinner"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9" stroke-width="3" />
          </svg>
          {{ loading ? "研究进行中..." : "开始研究" }}
        </span>
      </button>
      <slot name="actions"></slot>
    </div>
  </form>
</template>

<script lang="ts" setup>
import { reactive, watch, ref } from "vue";

const props = defineProps<{
  loading: boolean;
  initialTopic?: string;
}>();

const emit = defineEmits<{
  (e: "submit", payload: { topic: string; searchApi: string }): void;
}>();

const fileInput = ref<HTMLInputElement | null>(null);
const isUploading = ref(false);
const uploadStatus = ref("");
const availableSkills = ref<any[]>([]);
const showSkills = ref(false);

const toggleSkills = () => {
    showSkills.value = !showSkills.value;
};

const fetchSkills = async () => {
    try {
        const res = await fetch("http://localhost:8000/skills");
        if (res.ok) {
            const data = await res.json();
            availableSkills.value = data.skills || [];
        }
    } catch (e) {
        console.error("Failed to fetch skills", e);
    }
};

const toggleSkill = async (name: string, event: Event) => {
    const target = event.target as HTMLInputElement;
    const enabled = target.checked;
    try {
        await fetch(`http://localhost:8000/skills/${name}/toggle?enabled=${enabled}`, {
            method: "POST"
        });
    } catch (e) {
        console.error("Failed to toggle skill", e);
        target.checked = !enabled; // Revert on error
    }
};

// Initial fetch
fetchSkills();

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
    uploadStatus.value = "上传中...";
    try {
        const response = await fetch("http://localhost:8000/upload", {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) throw new Error("Upload failed");
        
        const result = await response.json();
        uploadStatus.value = `已上传: ${result.filename}`;
    } catch (e: any) {
        uploadStatus.value = "上传失败";
        console.error(e);
        setTimeout(() => { uploadStatus.value = ""; }, 3000);
    } finally {
        isUploading.value = false;
        if (target) target.value = ""; // Reset input
    }
};

const searchOptions = [
  "advanced",
  "duckduckgo",
  "tavily",
  "perplexity",
  "searxng",
];

const form = reactive({
  topic: props.initialTopic || "",
  searchApi: "",
});

watch(
  () => props.initialTopic,
  (newTopic) => {
    if (newTopic) {
      form.topic = newTopic;
    }
  }
);

const handleSubmit = () => {
  if (!form.topic.trim()) return;
  emit("submit", {
    topic: form.topic.trim(),
    searchApi: form.searchApi,
  });
};
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field span {
  font-weight: 600;
  color: #475569;
}

textarea,
select {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.92);
  color: #1f2937;
  font-size: 14px;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
  width: 100%;
  box-sizing: border-box;
}

textarea:focus,
select:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.65);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
  background: #ffffff;
}

textarea:disabled,
select:disabled {
  opacity: 0.7;
  cursor: not-allowed;
  background: #f1f5f9;
}

.options {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.skills-section {
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.6);
  overflow: hidden;
}

.skills-header {
  padding: 14px 16px;
  display: flex;
  align-items: center;
  cursor: pointer;
  gap: 10px;
  user-select: none;
}

.skills-header .title {
  font-weight: 600;
  color: #475569;
  flex: 1;
}

.skills-header .subtitle {
  font-size: 12px;
  color: #94a3b8;
}

.skills-header .arrow {
  transition: transform 0.3s;
  color: #64748b;
}

.skills-header.expanded .arrow {
  transform: rotate(180deg);
}

.skills-list {
  padding: 0 16px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skill-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.skill-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.skill-name {
  font-weight: 500;
  font-size: 14px;
  color: #1e293b;
}

.skill-desc {
  font-size: 12px;
  color: #64748b;
}

/* Toggle Switch */
.switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 20px;
}

.switch input { 
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #cbd5e1;
  transition: .4s;
  border-radius: 20px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background-color: white;
  transition: .4s;
  border-radius: 50%;
}

input:checked + .slider {
  background-color: #3b82f6;
}

input:checked + .slider:before {
  transform: translateX(20px);
}

.option {
  flex: 1;
  min-width: 140px;
}

.upload-wrapper {
  position: relative;
  width: 100%;
}

.file-input {
  display: none;
}

.upload-trigger {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px dashed rgba(148, 163, 184, 0.6);
  background: rgba(255, 255, 255, 0.5);
  color: #64748b;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.2s;
  box-sizing: border-box;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.upload-trigger:hover:not(.disabled) {
  background: rgba(255, 255, 255, 0.9);
  border-color: #3b82f6;
  color: #3b82f6;
}

.upload-trigger.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.submit {
  align-self: flex-start;
  padding: 12px 24px;
  border-radius: 16px;
  border: none;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, opacity 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  position: relative;
}

.submit-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.submit .spinner {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: rgba(255, 255, 255, 0.85);
  stroke-linecap: round;
  animation: spin 1s linear infinite;
}

.submit:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.submit:not(:disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.28);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
