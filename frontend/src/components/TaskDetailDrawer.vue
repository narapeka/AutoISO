<script setup lang="ts">
import { computed } from "vue";

import type { EventRecord, JobRecord } from "../types";
import { formatEventLevel, formatJobSource, formatJobStatus, formatJobStatusHint } from "../utils/labels";

const props = defineProps<{
  job: JobRecord | null;
  events: EventRecord[];
}>();

defineEmits<{
  close: [];
}>();

const title = computed(() => props.job?.torrent_name || "任务详情");
</script>

<template>
  <aside v-if="job" class="drawer">
    <div class="drawer-header">
      <div>
        <h2>{{ title }}</h2>
        <p>{{ formatJobSource(job.source_type) }} · {{ formatJobStatus(job.status) }}</p>
        <p class="muted">{{ formatJobStatusHint(job.status) }}</p>
      </div>
      <button class="ghost-button" @click="$emit('close')">关闭</button>
    </div>

    <div class="drawer-section">
      <h3>来源信息</h3>
      <p><strong>路径：</strong> {{ job.source_path }}</p>
      <p><strong>自动上传：</strong> {{ job.auto_upload ? "开启" : "关闭" }}</p>
      <p v-if="job.upload_target_path"><strong>上传目标：</strong> {{ job.upload_target_path }}</p>
    </div>

    <div class="drawer-section">
      <h3>打包日志</h3>
      <pre>{{ job.pack_log || "暂时没有打包日志。" }}</pre>
    </div>

    <div class="drawer-section">
      <h3>最近事件</h3>
      <ul class="events mini">
        <li v-for="event in events" :key="event.id">
          <strong>{{ formatEventLevel(event.level) }}</strong>
          <span>{{ event.message }}</span>
        </li>
      </ul>
    </div>
  </aside>
</template>
