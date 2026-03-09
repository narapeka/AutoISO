<script setup lang="ts">
import { onMounted, ref } from "vue";

import { api } from "../services/api";
import type { EventRecord, SystemStatus } from "../types";
import { formatEventLevel } from "../utils/labels";

const status = ref<SystemStatus | null>(null);
const events = ref<EventRecord[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

const LOG_LIMIT = 200;

function logLines(): string {
  return events.value
    .map((e) => {
      const ts = new Date(e.created_at).toLocaleString("sv-SE");
      return `[${ts}] ${formatEventLevel(e.level)} ${e.message}`;
    })
    .join("\n");
}

async function refresh(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [statusResult, eventsResult] = await Promise.all([
      api.health(),
      api.listEvents(undefined, LOG_LIMIT),
    ]);
    status.value = statusResult;
    events.value = eventsResult;
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
  }
}

onMounted(refresh);
</script>

<template>
  <section class="view dashboard-view">
    <div class="view-header">
      <div>
        <h1>仪表盘</h1>
      </div>
      <div class="toolbar">
        <button @click="refresh" :disabled="loading">刷新</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="stat-grid" v-if="status">
      <article class="stat-card">
        <span>qBittorrent</span>
        <strong :class="status.qbittorrent_connected ? 'ok' : 'bad'">
          {{ status.qbittorrent_connected ? "已连接" : "未连接" }}
        </strong>
      </article>
      <article class="stat-card">
        <span>CloudDrive2</span>
        <strong :class="status.clouddrive_connected ? 'ok' : 'bad'">
          {{ status.clouddrive_connected ? "已连接" : "未连接" }}
        </strong>
      </article>
      <article class="stat-card">
        <span>队列</span>
        <strong>{{ status.queued_jobs }}</strong>
      </article>
      <article class="stat-card">
        <span>活动上传</span>
        <strong>{{ status.active_uploads }}</strong>
      </article>
    </div>

    <section class="panel log-view-panel">
      <div class="panel-header">
        <h2>日志</h2>
      </div>
      <pre class="log-view"><code>{{ logLines() }}</code></pre>
    </section>
  </section>
</template>

<style scoped>
.log-view-panel {
  margin-top: 1rem;
}
.log-view {
  margin: 0;
  padding: 0.75rem 1rem;
  max-height: 42vh;
  overflow: auto;
  font-family: ui-monospace, "Cascadia Code", "Source Code Pro", Menlo, monospace;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: #94a3b8;
  background: rgba(2, 6, 23, 0.5);
  border-radius: 12px;
}
.log-view code {
  white-space: pre-wrap;
  word-break: break-all;
}

/* Mobile: compact header/panels, 2x2 status grid, log gets more vertical space */
@media (max-width: 980px) {
  .dashboard-view {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    min-height: calc(100vh - 4rem);
    padding: 0.35rem 0.5rem;
  }
  .dashboard-view .view-header {
    padding: 0.2rem 0;
    margin-bottom: 0;
    flex: 0 0 auto;
  }
  .dashboard-view .view-header h1 {
    font-size: 1.15rem;
  }
  .dashboard-view .stat-grid {
    flex: 0 0 auto;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.3rem;
  }
  .dashboard-view .stat-card {
    padding: 0.28rem 0.35rem;
    border-radius: 8px;
  }
  .dashboard-view .stat-card span {
    font-size: 0.65rem;
    line-height: 1.15;
  }
  .dashboard-view .stat-card strong {
    margin-top: 0.1rem;
    font-size: 0.85rem;
  }
  .dashboard-view .log-view-panel {
    flex: 1 1 0;
    min-height: 0;
    margin-top: 0;
    padding: 0.35rem 0.45rem;
    border-radius: 10px;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .dashboard-view .log-view-panel .panel-header {
    padding: 0;
    flex: 0 0 auto;
  }
  .dashboard-view .log-view-panel h2 {
    font-size: 0.8125rem;
  }
  .dashboard-view .log-view {
    flex: 1;
    min-height: min(45vh, 280px);
    max-height: none;
    padding: 0.35rem 0.45rem;
    font-size: 0.75rem;
    line-height: 1.4;
    border-radius: 8px;
    overflow: auto;
  }
}
</style>
