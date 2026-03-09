<script setup lang="ts">
import { computed, ref } from "vue";

import { api } from "../services/api";
import type { QBTaskSummary } from "../types";

const props = defineProps<{
  open: boolean;
  completedTorrents: QBTaskSummary[];
}>();

const emit = defineEmits<{
  close: [];
  created: [];
}>();

const selectedHashes = ref<Set<string>>(new Set());
const busy = ref(false);
const error = ref<string | null>(null);

const availableTorrents = computed(() =>
  props.completedTorrents.filter((item) => !item.already_known),
);

function toggle(hash: string): void {
  const next = new Set(selectedHashes.value);
  if (next.has(hash)) next.delete(hash);
  else next.add(hash);
  selectedHashes.value = next;
}

function onToggleAll(e: Event): void {
  const checked = (e.target as HTMLInputElement)?.checked ?? false;
  if (checked) {
    selectedHashes.value = new Set(availableTorrents.value.map((t) => t.torrent_hash));
  } else {
    selectedHashes.value = new Set();
  }
}

const allSelected = computed(
  () =>
    availableTorrents.value.length > 0 &&
    selectedHashes.value.size === availableTorrents.value.length,
);

async function submit(): Promise<void> {
  const hashes = Array.from(selectedHashes.value);
  if (hashes.length === 0) {
    error.value = "请至少选择一个 BDMV 种子。";
    return;
  }
  busy.value = true;
  error.value = null;
  try {
    for (const hash of hashes) {
      await api.createManualQbTask(hash, true);
    }
    emit("created");
    emit("close");
    selectedHashes.value = new Set();
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    busy.value = false;
  }
}

function onClose(): void {
  selectedHashes.value = new Set();
  error.value = null;
  emit("close");
}
</script>

<template>
  <div v-if="open" class="dialog-backdrop" @click.self="onClose">
    <section class="qb-dialog">
      <header class="qb-dialog-header">
        <h2 class="qb-dialog-title">qB 手动</h2>
        <p class="qb-dialog-desc">从已完成的 BDMV 种子中多选，批量创建任务（创建后自动上传）。</p>
        <button type="button" class="qb-dialog-close" aria-label="关闭" @click="onClose">×</button>
      </header>

      <div v-if="availableTorrents.length === 0" class="qb-dialog-empty muted">
        暂无可选种子，请确保 qBittorrent 中有已完成的 BDMV 且未被本系统收录。
      </div>
      <template v-else>
        <div class="qb-dialog-toolbar">
          <label class="qb-check-wrap">
            <input type="checkbox" :checked="allSelected" @change="onToggleAll" />
            <span class="qb-checkbox" aria-hidden="true"></span>
            <span class="qb-check-label">全选</span>
          </label>
        </div>
        <ul class="qb-torrent-list">
          <li
            v-for="item in availableTorrents"
            :key="item.torrent_hash"
            class="qb-torrent-row"
            :class="{ selected: selectedHashes.has(item.torrent_hash) }"
          >
            <label class="qb-torrent-label">
              <input
                type="checkbox"
                :checked="selectedHashes.has(item.torrent_hash)"
                @change="toggle(item.torrent_hash)"
              />
              <span class="qb-checkbox" aria-hidden="true"></span>
              <span class="qb-torrent-name">{{ item.name }}</span>
            </label>
            <span class="qb-torrent-path muted">{{ item.source_path }}</span>
          </li>
        </ul>
      </template>

      <p v-if="error" class="error">{{ error }}</p>

      <footer class="qb-dialog-footer">
        <button type="button" class="qb-btn-secondary" @click="onClose">取消</button>
        <button
          type="button"
          class="qb-btn-primary"
          :disabled="busy || availableTorrents.length === 0 || selectedHashes.size === 0"
          @click="submit"
        >
          {{ busy ? "创建中…" : `创建任务（已选 ${selectedHashes.size} 个）` }}
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.qb-dialog {
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

.qb-dialog-header {
  position: relative;
  padding-right: 2rem;
  flex-shrink: 0;
}

.qb-dialog-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #f1f5f9;
  letter-spacing: -0.02em;
}

.qb-dialog-desc {
  margin: 0.35rem 0 0;
  font-size: 0.8125rem;
  line-height: 1.45;
  color: #94a3b8;
}

.qb-dialog-close {
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

.qb-dialog-close:hover {
  color: #f1f5f9;
  background: rgba(148, 163, 184, 0.15);
}

.qb-dialog-empty {
  padding: 1rem;
  font-size: 0.875rem;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.06);
}

.qb-dialog-toolbar {
  flex-shrink: 0;
}

.qb-check-wrap,
.qb-torrent-label {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  user-select: none;
}

.qb-check-wrap {
  padding: 0.25rem 0;
}

.qb-torrent-label {
  width: 100%;
  align-items: flex-start;
  gap: 0.6rem;
}

.qb-check-wrap input,
.qb-torrent-label input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.qb-checkbox {
  position: relative;
  flex-shrink: 0;
  display: inline-block;
  width: 1.125rem;
  height: 1.125rem;
  border: 2px solid rgba(148, 163, 184, 0.35);
  border-radius: 5px;
  background: rgba(15, 23, 42, 0.6);
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}

.qb-check-wrap input:checked + .qb-checkbox,
.qb-torrent-label input:checked + .qb-checkbox {
  border-color: #3b82f6;
  background: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
}

.qb-checkbox::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 45%;
  width: 0.35rem;
  height: 0.65rem;
  margin-left: -0.2rem;
  margin-top: -0.4rem;
  border: solid #fff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg) scale(0);
  transition: transform 0.15s;
}

.qb-check-wrap input:checked + .qb-checkbox::after,
.qb-torrent-label input:checked + .qb-checkbox::after {
  transform: rotate(45deg) scale(1);
}

.qb-check-label {
  font-size: 0.875rem;
  color: #94a3b8;
}

.qb-torrent-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 38vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  flex: 1;
  min-height: 0;
}

.qb-torrent-row {
  padding: 0.65rem 0.75rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.08);
  background: rgba(30, 41, 59, 0.4);
  transition: border-color 0.15s, background 0.15s;
}

.qb-torrent-row:hover {
  border-color: rgba(148, 163, 184, 0.18);
  background: rgba(30, 41, 59, 0.55);
}

.qb-torrent-row.selected {
  border-color: rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.08);
}

.qb-torrent-name {
  font-size: 0.9rem;
  font-weight: 500;
  color: #e2e8f0;
  line-height: 1.35;
  word-break: break-word;
}

.qb-torrent-path {
  display: block;
  font-size: 0.75rem;
  margin-top: 0.35rem;
  margin-left: 1.75rem;
  line-height: 1.3;
  color: #64748b;
  word-break: break-all;
}

.qb-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  padding-top: 0.25rem;
  flex-shrink: 0;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
}

.qb-btn-secondary,
.qb-btn-primary {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, opacity 0.15s;
}

.qb-btn-secondary {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(148, 163, 184, 0.1);
  color: #cbd5e1;
}

.qb-btn-secondary:hover {
  background: rgba(148, 163, 184, 0.18);
  border-color: rgba(148, 163, 184, 0.35);
}

.qb-btn-primary {
  border: none;
  background: #3b82f6;
  color: #fff;
}

.qb-btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.qb-btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
