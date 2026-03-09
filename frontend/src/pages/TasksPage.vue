<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import FolderPickerDialog from "../components/FolderPickerDialog.vue";
import QbManualDialog from "../components/QbManualDialog.vue";
import TaskDetailDrawer from "../components/TaskDetailDrawer.vue";
import { api } from "../services/api";
import type { EventRecord, JobRecord, JobStatus, QBTaskSummary, SystemStatus } from "../types";
import { formatJobSource, formatJobStatus } from "../utils/labels";

const jobs = ref<JobRecord[]>([]);
const completedTorrents = ref<QBTaskSummary[]>([]);
const selectedJob = ref<JobRecord | null>(null);
const selectedEvents = ref<EventRecord[]>([]);
const statusFilter = ref("all");
const sourceFilter = ref("all");
const search = ref("");
const qbDialogOpen = ref(false);
const folderDialogOpen = ref(false);
const loading = ref(false);
const error = ref<string | null>(null);

const systemStatus = ref<SystemStatus | null>(null);
const createTaskOpen = ref(false);
const mobileFiltersOpen = ref(false);

const pollInterval = ref(60);
const autoImportMode = ref("full_auto");
const savingSettings = ref(false);

/** 筛选时「写入挂载目录中」同时包含 copying_to_mount 与 waiting_for_clouddrive_task */
const COPYING_STATUSES: JobStatus[] = ["copying_to_mount", "waiting_for_clouddrive_task"];

const filteredJobs = computed(() =>
  jobs.value.filter((job) => {
    if (statusFilter.value !== "all") {
      if (statusFilter.value === "copying_to_mount") {
        if (!COPYING_STATUSES.includes(job.status)) return false;
      } else if (job.status !== statusFilter.value) {
        return false;
      }
    }
    if (sourceFilter.value !== "all" && job.source_type !== sourceFilter.value) return false;
    if (search.value && !`${job.torrent_name} ${job.source_path}`.toLowerCase().includes(search.value.toLowerCase())) {
      return false;
    }
    return true;
  }),
);

const ACTIVE_STATUSES: JobStatus[] = ["packing", "copying_to_mount", "waiting_for_clouddrive_task", "uploading"];

function statusPillClass(status: JobStatus): string {
  if (status === "imported") return "status-pill status-imported";
  if (status === "pending") return "status-pill status-pending";
  if (ACTIVE_STATUSES.includes(status)) return "status-pill status-active";
  if (status === "packed") return "status-pill status-packed";
  if (status === "completed") return "status-pill status-completed";
  if (status === "failed") return "status-pill status-failed";
  if (status === "cancelled") return "status-pill status-cancelled";
  return "status-pill";
}

/** 打包进度 0–100，仅 packing 时有效 */
function packPercent(job: JobRecord): number | null {
  if (job.status !== "packing") return null;
  if (job.pack_progress_percent == null) return null;
  return Math.max(0, Math.min(100, job.pack_progress_percent));
}

/** 写入挂载或 CD2 上传进度 0–100 */
function copyOrUploadPercent(job: JobRecord): number | null {
  if (job.status !== "copying_to_mount" && job.status !== "uploading") return null;
  if (!job.upload_total_bytes || job.upload_total_bytes <= 0) return null;
  if (job.upload_bytes == null || job.upload_bytes < 0) return null;
  const ratio = job.upload_bytes / job.upload_total_bytes;
  return Math.round(Math.max(0, Math.min(1, ratio)) * 100);
}

/** 当前任务是否显示进度条及百分比（打包 / 写入挂载 / 上传） */
function progressPercent(job: JobRecord): number | null {
  const pack = packPercent(job);
  if (pack !== null) return pack;
  return copyOrUploadPercent(job);
}

/** 进度条文案：打包中 / 写入挂载中 / 上传中 */
function progressLabel(job: JobRecord): string {
  if (job.status === "packing") return "打包";
  if (job.status === "copying_to_mount" || job.status === "waiting_for_clouddrive_task") return "写入挂载";
  if (job.status === "uploading") return "上传";
  return "";
}

async function refresh(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [jobsResult, completedResult, statusResult] = await Promise.all([
      api.listJobs(),
      api.listCompletedQbTasks(),
      api.health(),
    ]);
    jobs.value = jobsResult;
    completedTorrents.value = completedResult;
    systemStatus.value = statusResult;
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
  }
}

/** 仅拉取任务列表（用于轮询进度，不显示 loading） */
async function refreshJobsOnly(): Promise<void> {
  try {
    jobs.value = await api.listJobs();
  } catch {
    /* ignore */
  }
}

async function loadSettings(): Promise<void> {
  try {
    const s = await api.getSettings();
    pollInterval.value = s.qbittorrent_poll_interval_seconds;
    autoImportMode.value = s.auto_import_mode;
  } catch { /* ignore, non-critical */ }
}

async function saveImportSettings(): Promise<void> {
  savingSettings.value = true;
  try {
    await api.saveSettings({
      qbittorrent_poll_interval_seconds: pollInterval.value,
      auto_import_mode: autoImportMode.value,
    } as any);
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    savingSettings.value = false;
  }
}

let settingsDebounce: ReturnType<typeof setTimeout> | null = null;
function scheduleSettingsSave() {
  if (settingsDebounce) clearTimeout(settingsDebounce);
  settingsDebounce = setTimeout(saveImportSettings, 600);
}

watch([pollInterval, autoImportMode], () => {
  scheduleSettingsSave();
});

async function toggleAutoPolling(): Promise<void> {
  if (!systemStatus.value) return;
  systemStatus.value = await api.setAutoPolling(!systemStatus.value.auto_polling_enabled);
}

async function openDetails(job: JobRecord): Promise<void> {
  selectedJob.value = await api.getJob(job.id);
  selectedEvents.value = await api.listEvents(job.id);
}

type JobAction = "start" | "retry" | "repack" | "reupload" | "upload" | "cancel" | "delete";

async function runAction(job: JobRecord, action: JobAction): Promise<void> {
  error.value = null;
  try {
    if (action === "start") await api.startJob(job.id);
    else if (action === "retry") await api.retryJob(job.id);
    else if (action === "repack") await api.repackJob(job.id);
    else if (action === "reupload") await api.reuploadJob(job.id);
    else if (action === "upload") await api.uploadJob(job.id);
    else if (action === "cancel") await api.cancelJob(job.id);
    else if (action === "delete") await api.deleteJob(job.id);
    await refresh();
    if (selectedJob.value?.id === job.id) {
      if (action === "delete") selectedJob.value = null;
      else await openDetails(job);
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  }
}

const progressPollInterval = ref<ReturnType<typeof setInterval> | null>(null);
const PROGRESS_POLL_MS = 2000;

onMounted(async () => {
  await Promise.all([refresh(), loadSettings()]);
  progressPollInterval.value = setInterval(() => {
    const hasActive = jobs.value.some((j) => ACTIVE_STATUSES.includes(j.status));
    if (hasActive) refreshJobsOnly();
  }, PROGRESS_POLL_MS);
});

onUnmounted(() => {
  if (progressPollInterval.value) {
    clearInterval(progressPollInterval.value);
    progressPollInterval.value = null;
  }
});
</script>

<template>
  <section class="view">
    <div class="view-header">
      <div>
        <h1>任务</h1>
      </div>
      <div class="toolbar">
        <button type="button" @click="createTaskOpen = true">创建任务</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="filters task-list-filters">
        <!-- Desktop: 4-column grid -->
        <input v-model="search" placeholder="搜索任务" class="filter-search desktop-only-cell" />
        <select v-model="statusFilter" class="filter-status desktop-only-cell">
          <option value="all">全部状态</option>
          <option value="imported">已导入</option>
          <option value="pending">待处理</option>
          <option value="packing">打包中</option>
          <option value="packed">已打包</option>
          <option value="copying_to_mount">写入挂载目录中</option>
          <option value="uploading">CloudDrive2 上传中</option>
          <option value="completed">已完成</option>
          <option value="failed">失败</option>
          <option value="cancelled">已取消</option>
        </select>
        <select v-model="sourceFilter" class="filter-source desktop-only-cell">
          <option value="all">全部来源</option>
          <option value="qb_auto">qB 自动任务</option>
          <option value="qb_manual">qB 手动任务</option>
          <option value="folder_manual">文件夹手动任务</option>
        </select>
        <button type="button" class="ghost-button task-list-refresh desktop-only-cell" @click="refresh" :disabled="loading">刷新</button>

        <!-- Mobile: 单行 + 可折叠 -->
        <div class="filter-mobile-row mobile-only">
          <input v-model="search" placeholder="搜索任务" class="filter-search" />
          <button
            type="button"
            class="ghost-button filter-toggle-mobile"
            :class="{ 'is-open': mobileFiltersOpen }"
            :aria-expanded="mobileFiltersOpen"
            @click="mobileFiltersOpen = !mobileFiltersOpen"
          >
            筛选
          </button>
          <button type="button" class="ghost-button task-list-refresh" @click="refresh" :disabled="loading">刷新</button>
        </div>
        <div class="filter-mobile-extra mobile-only" :class="{ 'is-open': mobileFiltersOpen }">
          <select v-model="statusFilter">
            <option value="all">全部状态</option>
            <option value="imported">已导入</option>
            <option value="pending">待处理</option>
            <option value="packing">打包中</option>
            <option value="packed">已打包</option>
            <option value="copying_to_mount">写入挂载目录中</option>
            <option value="uploading">CloudDrive2 上传中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
            <option value="cancelled">已取消</option>
          </select>
          <select v-model="sourceFilter">
            <option value="all">全部来源</option>
            <option value="qb_auto">qB 自动任务</option>
            <option value="qb_manual">qB 手动任务</option>
            <option value="folder_manual">文件夹手动任务</option>
          </select>
        </div>
      </div>

    <!-- Task Table -->
    <section class="panel task-list-panel">
      <div class="task-table">
        <div class="table-head table-head-check">
          <span class="th-source">来源</span>
          <span class="th-name">名称</span>
          <span class="th-status">状态</span>
          <span class="th-actions">操作</span>
        </div>
        <article v-for="job in filteredJobs" :key="job.id" class="table-row table-row-check">
          <span :class="['source-tag', `source-tag--${job.source_type}`]">{{ formatJobSource(job.source_type) }}</span>
          <button type="button" class="task-name-cell" @click="openDetails(job)">
            <span class="mobile-name-label">名称</span>
            <span class="task-name-title">{{ job.torrent_name }}</span>
            <span class="task-name-path">{{ job.source_path }}</span>
          </button>
          <div class="status-cell">
            <span class="mobile-status-label">状态</span>
            <span :class="statusPillClass(job.status)">{{ formatJobStatus(job.status) }}</span>
            <div
              v-if="progressPercent(job) !== null"
              class="status-progress"
              :aria-label="`${progressLabel(job)} ${progressPercent(job)}%`"
            >
              <div class="status-progress-track">
                <div class="status-progress-bar" :style="{ width: `${progressPercent(job) ?? 0}%` }" />
              </div>
              <span class="status-progress-label">{{ progressLabel(job) }} {{ progressPercent(job) }}%</span>
            </div>
          </div>
          <div class="row-actions row-actions-mobile-first">
            <!-- imported -->
            <template v-if="job.status === 'imported'">
              <button class="ghost-button action-start" @click="runAction(job, 'start')">开始</button>
              <button class="ghost-button action-danger" @click="runAction(job, 'cancel')">取消</button>
            </template>

            <!-- pending -->
            <template v-else-if="job.status === 'pending'">
              <button class="ghost-button action-danger" @click="runAction(job, 'cancel')">取消</button>
            </template>

            <!-- packing / copying / waiting / uploading -->
            <template v-else-if="ACTIVE_STATUSES.includes(job.status)">
              <span class="muted active-hint">处理中…</span>
            </template>

            <!-- packed -->
            <template v-else-if="job.status === 'packed'">
              <button class="ghost-button action-start" @click="runAction(job, 'upload')">上传</button>
              <button class="ghost-button" @click="runAction(job, 'repack')">重新打包</button>
              <button class="ghost-button action-danger" @click="runAction(job, 'cancel')">取消</button>
            </template>

            <!-- completed -->
            <template v-else-if="job.status === 'completed'">
              <button class="ghost-button" @click="runAction(job, 'repack')">重新打包</button>
              <button class="ghost-button" @click="runAction(job, 'reupload')">重新上传</button>
            </template>

            <!-- failed -->
            <template v-else-if="job.status === 'failed'">
              <button class="ghost-button action-start" @click="runAction(job, 'retry')">重试</button>
              <button class="ghost-button action-danger" @click="runAction(job, 'cancel')">取消</button>
            </template>

            <!-- cancelled -->
            <template v-else-if="job.status === 'cancelled'">
              <button class="ghost-button action-start" @click="runAction(job, 'retry')">重试</button>
              <button class="ghost-button action-danger" @click="runAction(job, 'delete')">删除</button>
            </template>
          </div>
        </article>
        <div v-if="filteredJobs.length === 0" class="table-empty muted">暂无任务。</div>
      </div>
    </section>

    <!-- 创建任务弹窗 -->
    <div v-if="createTaskOpen" class="create-task-backdrop" @click.self="createTaskOpen = false">
      <div class="create-task-dialog" role="dialog" aria-modal="true" aria-labelledby="create-task-title">
        <div class="create-task-header">
          <h2 id="create-task-title">创建任务</h2>
          <button type="button" class="create-task-close" aria-label="关闭" @click="createTaskOpen = false">×</button>
        </div>
        <div class="import-panel-body">
          <div class="import-block">
            <div class="import-block-head">
              <h3 class="import-block-title">qB 自动监控</h3>
              <label class="switch-monitor" v-if="systemStatus">
                <input
                  type="checkbox"
                  :checked="systemStatus.auto_polling_enabled"
                  @change="toggleAutoPolling"
                />
                <span class="switch-track"><span class="switch-thumb"></span></span>
                <span class="switch-label">{{ systemStatus.auto_polling_enabled ? "监控中" : "已关闭" }}</span>
              </label>
            </div>
            <div class="import-block-body" :class="{ 'import-block-body--disabled': !systemStatus?.auto_polling_enabled }">
              <label class="import-field-inline">
                <span class="import-field-label">轮询间隔</span>
                <span class="import-field-input-wrap">
                  <input
                    v-model.number="pollInterval"
                    type="number"
                    min="10"
                    class="import-input-num"
                    :disabled="!systemStatus?.auto_polling_enabled"
                  />
                  <span class="import-unit">秒</span>
                </span>
              </label>
              <label class="import-field-inline">
                <span class="import-field-label">导入后行为</span>
                <select
                  v-model="autoImportMode"
                  class="import-mode-select"
                  :disabled="!systemStatus?.auto_polling_enabled"
                >
                  <option value="import_only">仅导入</option>
                  <option value="pack_only">仅打包</option>
                  <option value="full_auto">打包并上传</option>
                </select>
              </label>
            </div>
          </div>
          <div class="import-block">
            <h3 class="import-block-title">手动导入</h3>
            <div class="import-block-actions">
              <button type="button" class="import-action-btn" @click="createTaskOpen = false; qbDialogOpen = true">从 qB 已完成列表</button>
              <button type="button" class="import-action-btn" @click="createTaskOpen = false; folderDialogOpen = true">从本地文件夹</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <QbManualDialog
      :open="qbDialogOpen"
      :completed-torrents="completedTorrents"
      @close="qbDialogOpen = false"
      @created="refresh"
    />
    <FolderPickerDialog
      :open="folderDialogOpen"
      @close="folderDialogOpen = false"
      @created="refresh"
    />
    <TaskDetailDrawer :job="selectedJob" :events="selectedEvents" @close="selectedJob = null" />
  </section>
</template>

<style scoped>
/* ── 创建任务弹窗 ── */
.create-task-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(2, 6, 23, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.create-task-dialog {
  width: 100%;
  max-width: 28rem;
  max-height: 90vh;
  overflow: auto;
  background: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 14px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
}

.create-task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.create-task-header h2 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #e2e8f0;
}

.create-task-close {
  width: 2rem;
  height: 2rem;
  padding: 0;
  font-size: 1.5rem;
  line-height: 1;
  color: #94a3b8;
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.create-task-close:hover {
  color: #e2e8f0;
  background: rgba(148, 163, 184, 0.1);
}

.create-task-dialog .import-panel-body {
  padding: 1rem 1.25rem 1.25rem;
  margin-top: 0;
}

.task-list-filters {
  grid-template-columns: 2fr 1fr 1fr auto;
  align-items: center;
}

.task-list-filters .mobile-only {
  display: none;
}

.task-list-refresh {
  justify-self: start;
}

/* 过滤栏控件：略小字号与高度 */
.task-list-filters input,
.task-list-filters select {
  font-size: 0.875rem;
  padding: 0.4rem 0.65rem;
  min-height: auto;
}
.task-list-filters .ghost-button {
  padding: 0.35rem 0.65rem;
  min-height: auto;
}

.filter-toggle-mobile.is-open {
  background: rgba(59, 130, 246, 0.18);
  color: #93c5fd;
}

/* ── Import Panel ── */
.import-panel-body {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.import-block {
  padding: 1rem 1.15rem;
  background: rgba(2, 6, 23, 0.35);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.import-block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.import-block-title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: #e2e8f0;
  letter-spacing: 0.01em;
}

.import-block-body {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.25rem 1.75rem;
}

.import-block-body--disabled {
  opacity: 0.55;
  pointer-events: none;
}

.import-field-inline {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.import-field-label {
  font-size: 0.8125rem;
  color: #94a3b8;
  font-weight: 500;
  white-space: nowrap;
}

.import-field-input-wrap {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.import-input-num {
  width: 4rem;
  padding: 0.4rem 0.5rem;
  font-size: 0.875rem;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.7);
  color: #e7edf7;
  text-align: center;
}

.import-unit {
  font-size: 0.8125rem;
  color: #94a3b8;
}

.import-mode-select {
  min-width: 8rem;
  padding: 0.4rem 0.65rem;
  font-size: 0.875rem;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.7);
  color: #e7edf7;
  cursor: pointer;
}

.import-block-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.import-action-btn {
  padding: 0.55rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(59, 130, 246, 0.15);
  color: #93c5fd;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  box-shadow: none;
}

.import-action-btn:hover {
  background: rgba(59, 130, 246, 0.25);
  border-color: rgba(59, 130, 246, 0.3);
  transform: none;
}

/* ── Toggle Switch ── */
.switch-monitor {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  user-select: none;
}
.switch-monitor input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}
.switch-label {
  font-size: 0.8125rem;
  color: #94a3b8;
}
.switch-track {
  position: relative;
  display: block;
  width: 2.25rem;
  height: 1.2rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.2);
  border: 1px solid rgba(148, 163, 184, 0.15);
  transition: background 0.2s, border-color 0.2s;
  flex-shrink: 0;
}
.switch-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: calc(1.2rem - 4px);
  height: calc(1.2rem - 4px);
  border-radius: 50%;
  background: #94a3b8;
  transition: transform 0.2s;
}
.switch-monitor:has(input:checked) .switch-track {
  background: rgba(59, 130, 246, 0.5);
  border-color: rgba(59, 130, 246, 0.5);
}
.switch-monitor:has(input:checked) .switch-thumb {
  transform: translateX(1.05rem);
  background: #3b82f6;
}

/* ── Table ── */
.table-head-check,
.table-row-check {
  display: grid;
  grid-template-columns: 0.6fr 3fr 0.6fr 1.5fr;
  align-items: center;
  gap: 0 0.75rem;
}

/* 表头与内容列对齐 */
.table-head-check > .th-source,
.table-row-check > .source-tag { justify-self: start; }
.table-head-check > .th-name,
.table-row-check > .task-name-cell { justify-self: start; }
.table-head-check > .th-status,
.table-row-check > .status-cell { justify-self: center; }
.table-head-check > .th-actions,
.table-row-check > .row-actions { justify-self: end; }

/* ── 来源 Tag ── */
.source-tag {
  display: inline-block;
  padding: 0.25rem 0.6rem;
  font-size: 0.8125rem;
  font-weight: 500;
  border-radius: 8px;
  white-space: nowrap;
}
.source-tag--qb_auto {
  background: rgba(59, 130, 246, 0.18);
  color: #93c5fd;
}
.source-tag--qb_manual {
  background: rgba(139, 92, 246, 0.18);
  color: #c4b5fd;
}
.source-tag--folder_manual {
  background: rgba(20, 184, 166, 0.18);
  color: #5eead4;
}

/* ── 任务名称（可点击查看详情，无背景无动效）── */
.task-name-cell {
  display: block;
  width: 100%;
  padding: 0;
  margin: 0;
  text-align: left;
  font: inherit;
  color: inherit;
  background: transparent;
  border: none;
  border-radius: 0;
  box-shadow: none;
  cursor: pointer;
  transition: none;
  -webkit-tap-highlight-color: transparent;
}
.task-name-cell:hover {
  transform: none;
}
.task-name-title {
  display: block;
  font-size: 0.875rem;
  font-weight: 600;
  color: #e2e8f0;
  line-height: 1.35;
}
.task-name-path {
  display: block;
  margin-top: 0.2rem;
  font-size: 0.8125rem;
  color: #94a3b8;
  line-height: 1.3;
}

.mobile-name-label,
.mobile-status-label {
  display: none;
}

/* ── Status Pill Colors ── */
.status-imported {
  background: rgba(148, 163, 184, 0.18);
  color: #cbd5e1;
}
.status-pending {
  background: rgba(251, 191, 36, 0.15);
  color: #fcd34d;
}
.status-active {
  background: rgba(59, 130, 246, 0.18);
  color: #93c5fd;
}
.status-packed {
  background: rgba(20, 184, 166, 0.18);
  color: #5eead4;
}
.status-completed {
  background: rgba(34, 197, 94, 0.18);
  color: #86efac;
}
.status-failed {
  background: rgba(239, 68, 68, 0.18);
  color: #fca5a5;
}
.status-cancelled {
  background: rgba(148, 163, 184, 0.12);
  color: #94a3b8;
}

.status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25rem;
}

/* 状态列：缩小字体与 pill 高度 */
.table-row-check .status-pill {
  font-size: 0.8125rem;
  min-width: 0;
  padding: 0.2rem 0.5rem;
}

.status-progress {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.status-progress-track {
  position: relative;
  flex: 1;
  height: 0.4rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.9);
  overflow: hidden;
}

.status-progress-bar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 0;
  border-radius: 999px;
  background: linear-gradient(90deg, #3b82f6, #22c55e);
  transition: width 0.25s ease-out;
}

.status-progress-label {
  font-size: 0.75rem;
  color: #93c5fd;
  white-space: nowrap;
}

/* ── Action Button Variants ── */
.action-start {
  background: rgba(59, 130, 246, 0.18);
  color: #93c5fd;
}
.action-danger {
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
}
.active-hint {
  font-size: 0.8125rem;
}

/* ── Empty State ── */
.table-empty {
  padding: 2rem;
  text-align: center;
  font-size: 0.875rem;
}

@media (max-width: 980px) {
  .view-header {
    margin-bottom: 0.25rem;
  }
  .view-header h1 {
    font-size: 1.5rem;
  }

  .task-tabs {
    margin-bottom: 0.75rem;
  }
  .task-tab {
    min-height: 3rem;
    font-size: 0.875rem;
  }

  .task-list-filters {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    padding: 0.25rem 0 0.35rem;
    width: 100%;
    box-sizing: border-box;
  }
  .task-list-filters .desktop-only-cell {
    display: none !important;
  }
  .task-list-filters .mobile-only {
    display: flex;
  }
  .filter-mobile-row {
    display: flex;
    width: 100%;
    min-width: 0;
    gap: 0.4rem;
    align-items: center;
  }
  .filter-mobile-row .filter-search {
    flex: 1;
    min-width: 0;
    width: 0;
  }
  .filter-mobile-row .task-list-refresh,
  .filter-mobile-row .filter-toggle-mobile {
    flex-shrink: 0;
  }
  .filter-mobile-extra.mobile-only {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.4rem;
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.2s ease-out;
    width: 100%;
    box-sizing: border-box;
  }
  .filter-mobile-extra.mobile-only.is-open {
    max-height: 6rem;
  }

  .import-block-body {
    flex-direction: column;
    align-items: flex-start;
  }
  .import-block-actions {
    width: 100%;
  }
  .import-action-btn {
    flex: 1;
    min-width: 0;
  }

  /* 移动端：隐藏表头，卡片式列表 */
  .table-head-check {
    display: none !important;
  }
  .table-row-check {
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-rows: auto auto auto;
    grid-template-areas:
      "card-head-mid card-head-right"
      "card-name card-name"
      "card-status card-status";
    gap: 0 0.5rem;
    align-items: center;
  }
  .table-row-check > .source-tag {
    grid-area: card-head-mid;
    justify-self: start;
  }
  .row-actions-mobile-first {
    grid-area: card-head-right;
    justify-self: end;
    flex-wrap: nowrap;
    gap: 0.35rem;
  }
  .table-row-check > .task-name-cell {
    grid-area: card-name;
    justify-self: stretch;
    text-align: left;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(148, 163, 184, 0.08);
  }
  .table-row-check > .status-cell {
    grid-area: card-status;
    justify-self: start;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(148, 163, 184, 0.08);
  }
  .mobile-name-label {
    display: block;
    font-size: 0.75rem;
    font-weight: 500;
    color: #94a3b8;
    margin-bottom: 0.2rem;
  }
  .mobile-status-label {
    display: inline;
    font-size: 0.75rem;
    font-weight: 500;
    color: #94a3b8;
    margin-right: 0.25rem;
  }
  /* 任务列表外层 panel：移动端缩小内边距，减少外框占位 */
  .task-list-panel {
    padding: 0.75rem 1rem;
    gap: 0.5rem;
  }
  .panel .task-table {
    gap: 0.5rem;
  }
  .table-row {
    padding: 1rem;
    border-radius: 14px;
    background: rgba(2, 6, 23, 0.4);
    border: 1px solid rgba(148, 163, 184, 0.1);
  }
  .table-row + .table-row {
    margin-top: 0.25rem;
  }
  .task-name-title {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .task-name-path {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
