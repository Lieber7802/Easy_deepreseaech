import { ref, computed } from 'vue';
import { runResearchStream, type ResearchStreamEvent } from '../services/api';

export interface Task {
  id: string;
  title: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  summary?: string;
  sources?: string[];
  intent?: string;
  logs?: string[];
  // Additional fields for display
  description?: string;
}

export function useResearch() {
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  
  // Data
  const tasks = ref<Map<string, Task>>(new Map());
  const reportMarkdown = ref('');
  const progressLogs = ref<string[]>([]);
  const activeTaskId = ref<string | null>(null);

  // Computed
  const taskList = computed(() => Array.from(tasks.value.values()));
  const activeTask = computed(() => activeTaskId.value ? tasks.value.get(activeTaskId.value) : null);
  const isResearchComplete = computed(() => !!reportMarkdown.value);

  // Actions
  const startResearch = async (topic: string, searchApi?: string) => {
    // Reset state
    isLoading.value = true;
    error.value = null;
    tasks.value.clear();
    reportMarkdown.value = '';
    progressLogs.value = [];
    activeTaskId.value = null;

    try {
      await runResearchStream(
        { topic, search_api: searchApi },
        (event) => {
          handleEvent(event);
        }
      );
    } catch (err: any) {
      error.value = err.message || 'Research failed unexpectedly';
      progressLogs.value.push(`Error: ${error.value}`);
    } finally {
      isLoading.value = false;
    }
  };

  const handleEvent = (event: ResearchStreamEvent) => {
    switch (event.type) {
      case 'status':
        if (typeof event.message === 'string') {
          progressLogs.value.push(event.message);
        }
        break;

      case 'todo_list':
        // Merge new tasks
        if (Array.isArray(event.tasks)) {
          event.tasks.forEach((t: any) => {
            const idStr = String(t.id);
            if (!tasks.value.has(idStr)) {
              tasks.value.set(idStr, {
                id: idStr,
                title: t.title || `Task ${idStr}`,
                status: t.status || 'pending',
                description: t.description || t.intent,
                sources: [],
                logs: []
              });
              progressLogs.value.push(`规划任务: ${t.title}`);
            }
          });
          // If no active task, select the first one
          if (!activeTaskId.value && event.tasks.length > 0) {
            activeTaskId.value = String(event.tasks[0].id);
          }
        }
        break;

      case 'task_status':
        const taskId = String(event.task_id);
        const task = tasks.value.get(taskId);
        if (task) {
          // Update status
          if (typeof event.status === 'string') {
             const newStatus = event.status as Task['status'];
            // Log state changes
            if (task.status !== newStatus) {
              if (newStatus === 'in_progress') {
                progressLogs.value.push(`开始执行: ${task.title}`);
              } else if (newStatus === 'completed') {
                progressLogs.value.push(`完成任务: ${task.title}`);
              } else if (newStatus === 'failed') {
                progressLogs.value.push(`任务失败: ${task.title}`);
              }
            }
            task.status = newStatus;
          }
          
          // Update metadata
          if (typeof event.summary === 'string') task.summary = event.summary;
          if (typeof event.intent === 'string') {
            task.intent = event.intent;
            // Add intent to task logs if not duplicate
            if (!task.logs) task.logs = [];
            if (!task.logs.includes(event.intent)) {
              task.logs.push(event.intent);
            }
          }
        }
        break;

      case 'sources':
        const sourceTaskId = String(event.task_id);
        const sourceTask = tasks.value.get(sourceTaskId);
        if (sourceTask && typeof event.latest_sources === 'string') {
          // Add sources
          if (!sourceTask.sources) sourceTask.sources = [];
          // Simple dedup
          if (!sourceTask.sources.includes(event.latest_sources)) {
            sourceTask.sources.push(event.latest_sources);
            if (!sourceTask.logs) sourceTask.logs = [];
            sourceTask.logs.push(`发现来源: ${event.latest_sources.substring(0, 50)}...`);
          }
        }
        break;
        
      case 'tool_call':
        const toolTaskId = String(event.task_id);
        const toolTask = tasks.value.get(toolTaskId);
        if (toolTask && typeof event.tool === 'string') {
            const logMsg = `调用工具: ${event.tool}`;
            if (!toolTask.logs) toolTask.logs = [];
            // Only add if not the last log (prevent spamming same tool)
            if (toolTask.logs[toolTask.logs.length - 1] !== logMsg) {
                 toolTask.logs.push(logMsg);
            }
        }
        break;

      case 'final_report':
        if (typeof event.report === 'string') {
          reportMarkdown.value = event.report;
          progressLogs.value.push('最终报告生成完毕');
          
          // Force complete any pending/in_progress tasks
          tasks.value.forEach(t => {
            if (t.status === 'pending' || t.status === 'in_progress') {
              t.status = 'completed'; 
            }
          });
        }
        break;
        
      case 'error':
         const errorMsg = typeof event.detail === 'string' ? event.detail : 'Unknown error';
         error.value = errorMsg;
         progressLogs.value.push(`Error: ${errorMsg}`);
         break;
    }
  };

  const resetResearch = () => {
    isLoading.value = false;
    error.value = null;
    tasks.value.clear();
    reportMarkdown.value = '';
    progressLogs.value = [];
    activeTaskId.value = null;
  };

  return {
    isLoading,
    error,
    tasks: taskList,
    activeTaskId,
    activeTask,
    reportMarkdown,
    progressLogs,
    isResearchComplete,
    startResearch,
    resetResearch
  };
}
