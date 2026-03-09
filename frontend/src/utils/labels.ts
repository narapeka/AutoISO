import type { JobSourceType, JobStatus } from "../types";

const sourceLabels: Record<JobSourceType, string> = {
  qb_auto: "qB 自动任务",
  qb_manual: "qB 手动任务",
  folder_manual: "文件夹手动任务",
};

const statusLabels: Record<JobStatus, string> = {
  imported: "已导入",
  pending: "待处理",
  packing: "打包中",
  packed: "已打包",
  copying_to_mount: "写入挂载目录中",
  waiting_for_clouddrive_task: "写入挂载目录中",
  uploading: "CloudDrive2 上传中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const eventLevelLabels: Record<string, string> = {
  INFO: "信息",
  WARNING: "警告",
  ERROR: "错误",
  DEBUG: "调试",
};

export function formatJobSource(source: JobSourceType): string {
  return sourceLabels[source] ?? source;
}

export function formatJobStatus(status: JobStatus): string {
  return statusLabels[status] ?? status;
}

export function formatEventLevel(level: string): string {
  return eventLevelLabels[level] ?? level;
}

export function formatJobStatusHint(status: JobStatus): string {
  const hints: Record<JobStatus, string> = {
    imported: "任务已导入，等待用户确认后开始处理。",
    pending: "任务已入队，等待开始处理。",
    packing: "正在校验源目录并生成 ISO 文件。",
    packed: "ISO 已生成，等待手动上传或后续操作。",
    copying_to_mount: "正在把 ISO 写入挂载目录并等待 CloudDrive2 接管上传。",
    waiting_for_clouddrive_task: "正在把 ISO 写入挂载目录并等待 CloudDrive2 接管上传。",
    uploading: "CloudDrive2 已接管任务，正在上传到远端存储。",
    completed: "上传已确认完成，本地打包文件已清理。",
    failed: "任务处理失败，请查看日志后重试。",
    cancelled: "任务已被手动取消。",
  };
  return hints[status] ?? status;
}
