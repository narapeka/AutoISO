<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import FolderPickerDialog from "../components/FolderPickerDialog.vue";
import { api } from "../services/api";
import type { SettingsModel } from "../types";

const folderPickerOpen = ref(false);

const settings = reactive<SettingsModel>({
  log_level: "INFO",
  qbittorrent_url: "http://localhost:8080",
  qbittorrent_username: "admin",
  qbittorrent_password: "adminadmin",
  qbittorrent_poll_interval_seconds: 60,
  qbittorrent_category_filter: "",
  qbittorrent_tag_filter: "",
  clouddrive_url: "localhost:19798",
  clouddrive_upload_bandwidth_mb: 5,
  clouddrive_username: "admin",
  clouddrive_password: "password",
  clouddrive_target_path: "/CloudDrive/115open/我的上传",
  auto_import_mode: "full_auto",
});

const loading = ref(false);
const error = ref<string | null>(null);
const saved = ref(false);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    Object.assign(settings, await api.getSettings());
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
  }
}

async function save(): Promise<void> {
  loading.value = true;
  error.value = null;
  saved.value = false;
  try {
    await api.saveSettings({ ...settings });
    Object.assign(settings, await api.getSettings());
    saved.value = true;
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="view">
    <div class="view-header">
      <div>
        <h1>设置</h1>
      </div>
      <div class="toolbar">
        <button type="button" @click="save" :disabled="loading">
          {{ loading ? "保存中…" : "保存设置" }}
        </button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="saved" class="ok">设置已保存。</p>

    <div class="settings-grid">
      <section class="panel">
        <div class="panel-header"><h2>qBittorrent</h2></div>
        <label class="field"><span>URL</span><input v-model="settings.qbittorrent_url" /></label>
        <label class="field"><span>用户名</span><input v-model="settings.qbittorrent_username" /></label>
        <label class="field"><span>密码</span><input v-model="settings.qbittorrent_password" type="password" /></label>
        <label class="field"><span>分类过滤</span><input v-model="settings.qbittorrent_category_filter" placeholder="qB分类，多个用逗号分隔" /></label>
        <label class="field"><span>标签过滤</span><input v-model="settings.qbittorrent_tag_filter" placeholder="qB标签，多个用逗号分隔" /></label>
        <p class="field-hint muted">过滤仅对「任务」页开启 qB 监控后自动发现的种子生效。</p>
      </section>

      <section class="panel">
        <div class="panel-header"><h2>CloudDrive2</h2></div>
        <label class="field"><span>地址</span><input v-model="settings.clouddrive_url" /></label>
        <label class="field"><span>用户名</span><input v-model="settings.clouddrive_username" /></label>
        <label class="field"><span>密码</span><input v-model="settings.clouddrive_password" type="password" /></label>
        <label class="field">
          <span>挂载目标路径</span>
          <div class="field-with-picker">
            <input v-model="settings.clouddrive_target_path" />
            <button type="button" class="picker-trigger" @click="folderPickerOpen = true">浏览</button>
          </div>
        </label>
        <FolderPickerDialog
          :open="folderPickerOpen"
          mode="path"
          @close="folderPickerOpen = false"
          @select="(path: string) => { settings.clouddrive_target_path = path; folderPickerOpen = false; }"
        />
        <label class="field"><span>上传带宽分配（MB/s）</span><input v-model.number="settings.clouddrive_upload_bandwidth_mb" type="number" /></label>
      </section>
    </div>
  </section>
</template>

<style scoped>
.field-with-picker {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.field-with-picker input {
  flex: 1;
  min-width: 0;
}
.picker-trigger {
  flex-shrink: 0;
  padding: 0.4rem 0.75rem;
  font-size: 0.875rem;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  background: rgba(148, 163, 184, 0.1);
  color: #cbd5e1;
  cursor: pointer;
}
.picker-trigger:hover {
  background: rgba(148, 163, 184, 0.18);
}
</style>
