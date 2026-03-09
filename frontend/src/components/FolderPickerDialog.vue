<script setup lang="ts">
import { ref, watch } from "vue";

import { api } from "../services/api";

const props = withDefaults(
  defineProps<{ open: boolean; mode?: "task" | "path" }>(),
  { mode: "task" },
);

const emit = defineEmits<{
  close: [];
  created: [];
  select: [path: string];
}>();

/** Empty = system root (on Windows: drives; on Linux/Docker: /). */
const ROOT = "";

const currentPath = ref(ROOT);
const entries = ref<{ name: string; path: string; is_dir: boolean }[]>([]);
const hasBdmv = ref(false);
const loading = ref(false);
const busy = ref(false);
const error = ref<string | null>(null);

async function loadDir(path: string): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const res = await api.browse(path);
    currentPath.value = res.path;
    entries.value = res.entries;
    const pathStr = res.path;
    if (props.mode === "path") {
      hasBdmv.value = !!(pathStr && pathStr !== "/");
    } else if (!pathStr || pathStr === "/") {
      hasBdmv.value = false;
    } else {
      const check = await api.browseCheckBdmv(pathStr);
      hasBdmv.value = check.is_bdmv;
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
    entries.value = [];
    hasBdmv.value = false;
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      currentPath.value = ROOT;
      error.value = null;
      loadDir(ROOT);
    }
  },
);

function goTo(entry: { path: string }): void {
  loadDir(entry.path);
}

function goUp(): void {
  const p = currentPath.value.replace(/[/\\]+$/, "");
  if (!p || p === "/" || /^[A-Za-z]:$/i.test(p)) return;
  const sep = p.includes("\\") ? "\\" : "/";
  const parent = p.replace(/[/\\][^/\\]+$/, "") || (sep === "\\" ? "" : "/");
  loadDir(parent || ROOT);
}

function canGoUp(): boolean {
  const p = currentPath.value.replace(/[/\\]+$/, "");
  return !!p && p !== "/" && !/^[A-Za-z]:$/i.test(p);
}

async function confirm(): Promise<void> {
  if (props.mode === "path") {
    if (currentPath.value && currentPath.value !== "/") {
      emit("select", currentPath.value);
      emit("close");
    }
    return;
  }
  busy.value = true;
  error.value = null;
  try {
    await api.createManualFolderTask(currentPath.value, true);
    emit("created");
    emit("close");
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    busy.value = false;
  }
}

function onClose(): void {
  error.value = null;
  emit("close");
}
</script>

<template>
  <div v-if="open" class="folder-picker-backdrop" @click.self="onClose">
    <section class="folder-picker-dialog">
      <header class="folder-picker-header">
        <h2 class="folder-picker-title">{{ mode === 'path' ? '选择挂载目标路径' : '从文件夹创建' }}</h2>
        <p class="folder-picker-desc">{{ mode === 'path' ? '选择要作为 CloudDrive2 挂载目标的目录。' : '选择 BDMV 所在目录，在此目录创建任务（创建后自动上传）。' }}</p>
        <button type="button" class="folder-picker-close" aria-label="关闭" @click="onClose">×</button>
      </header>

      <div class="folder-picker-breadcrumb">
        <button
          v-if="canGoUp()"
          type="button"
          class="folder-picker-up"
          @click="goUp"
        >
          ← 上一级
        </button>
        <span class="folder-picker-path muted">{{ currentPath || "（根目录）" }}</span>
      </div>

      <div v-if="loading" class="folder-picker-loading muted">加载中…</div>
      <ul v-else class="folder-picker-list">
        <li
          v-for="entry in entries"
          :key="entry.path"
          class="folder-picker-row"
        >
          <button type="button" class="folder-picker-entry" @click="goTo(entry)">
            <span class="folder-picker-icon">📁</span>
            <span class="folder-picker-name">{{ entry.name }}</span>
          </button>
        </li>
        <li v-if="entries.length === 0 && !loading" class="muted folder-picker-empty">
          此目录下没有子文件夹
        </li>
      </ul>

      <p v-if="error" class="error">{{ error }}</p>

      <footer class="folder-picker-footer">
        <button type="button" class="folder-picker-btn-secondary" @click="onClose">
          取消
        </button>
        <button
          type="button"
          class="folder-picker-btn-primary"
          :disabled="busy || !currentPath || currentPath === '/' || !hasBdmv"
          @click="confirm"
        >
          {{ busy ? "创建中…" : (mode === 'path' ? "选择此目录" : "在此目录创建任务") }}
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.folder-picker-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.72);
  display: grid;
  place-items: center;
  z-index: 30;
  padding: 1rem;
}

.folder-picker-dialog {
  width: min(44rem, 100%);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: rgba(15, 23, 42, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  backdrop-filter: blur(20px);
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4);
}

.folder-picker-header {
  position: relative;
  padding-right: 2rem;
  flex-shrink: 0;
}

.folder-picker-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #f1f5f9;
}

.folder-picker-desc {
  margin: 0.35rem 0 0;
  font-size: 0.8125rem;
  line-height: 1.45;
  color: #94a3b8;
}

.folder-picker-close {
  position: absolute;
  top: -0.25rem;
  right: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #94a3b8;
  font-size: 1.35rem;
  line-height: 1;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}

.folder-picker-close:hover {
  color: #f1f5f9;
  background: rgba(148, 163, 184, 0.15);
}

.folder-picker-breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
  min-height: 2rem;
}

.folder-picker-up {
  padding: 0.35rem 0.6rem;
  font-size: 0.8125rem;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  background: rgba(148, 163, 184, 0.1);
  color: #cbd5e1;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s, border-color 0.15s;
}

.folder-picker-up:hover {
  background: rgba(148, 163, 184, 0.18);
  border-color: rgba(148, 163, 184, 0.35);
}

.folder-picker-path {
  font-size: 0.8125rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-picker-loading {
  padding: 1.5rem;
  text-align: center;
  font-size: 0.875rem;
}

.folder-picker-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 38vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
  min-height: 0;
}

.folder-picker-row {
  margin: 0;
}

.folder-picker-entry {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.75rem;
  text-align: left;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #e2e8f0;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.15s;
}

.folder-picker-entry:hover {
  background: rgba(148, 163, 184, 0.12);
}

.folder-picker-icon {
  flex-shrink: 0;
}

.folder-picker-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-picker-empty {
  padding: 1rem;
  font-size: 0.875rem;
}

.folder-picker-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  padding-top: 0.25rem;
  flex-shrink: 0;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
}

.folder-picker-btn-secondary,
.folder-picker-btn-primary {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
}

.folder-picker-btn-secondary {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(148, 163, 184, 0.1);
  color: #cbd5e1;
}

.folder-picker-btn-secondary:hover {
  background: rgba(148, 163, 184, 0.18);
}

.folder-picker-btn-primary {
  border: none;
  background: #3b82f6;
  color: #fff;
}

.folder-picker-btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.folder-picker-btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
