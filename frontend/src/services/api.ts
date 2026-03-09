import type {
  EventRecord,
  JobRecord,
  QBTaskSummary,
  SettingsModel,
  SystemStatus,
} from "../types";

const API_BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<SystemStatus>("/health"),
  listJobs: () => request<JobRecord[]>("/jobs"),
  getJob: (jobId: number) => request<JobRecord>(`/jobs/${jobId}`),
  listEvents: (jobId?: number, limit?: number) => {
    const params = new URLSearchParams();
    if (jobId != null) params.set("job_id", String(jobId));
    if (limit != null) params.set("limit", String(limit));
    const q = params.toString();
    return request<EventRecord[]>(q ? `/events?${q}` : "/events");
  },
  getSettings: () => request<SettingsModel>("/settings"),
  saveSettings: (values: SettingsModel) =>
    request<SettingsModel>("/settings", {
      method: "PUT",
      body: JSON.stringify({ values }),
    }),
  setAutoPolling: (enabled: boolean) =>
    request<SystemStatus>("/dashboard/auto-polling", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  listCompletedQbTasks: () => request<QBTaskSummary[]>("/qbittorrent/completed"),
  createManualQbTask: (torrentHash: string, autoUpload: boolean) =>
    request<JobRecord>("/jobs/manual/qbittorrent", {
      method: "POST",
      body: JSON.stringify({ torrent_hash: torrentHash, auto_upload: autoUpload }),
    }),
  browse: (path: string) =>
    request<{ path: string; entries: { name: string; path: string; is_dir: boolean }[] }>(
      `/browse?path=${encodeURIComponent(path)}`,
    ),
  browseCheckBdmv: (path: string) =>
    request<{ is_bdmv: boolean }>(`/browse/check-bdmv?path=${encodeURIComponent(path)}`),
  createManualFolderTask: (sourcePath: string, autoUpload: boolean) =>
    request<JobRecord>("/jobs/manual/folder", {
      method: "POST",
      body: JSON.stringify({ source_path: sourcePath, name: null, auto_upload: autoUpload }),
    }),
  uploadJob: (jobId: number) =>
    request<JobRecord>(`/jobs/${jobId}/upload`, { method: "POST" }),
  retryJob: (jobId: number) =>
    request<JobRecord>(`/jobs/${jobId}/retry`, { method: "POST" }),
  repackJob: (jobId: number) =>
    request<JobRecord>(`/jobs/${jobId}/repack`, { method: "POST" }),
  reuploadJob: (jobId: number) =>
    request<JobRecord>(`/jobs/${jobId}/reupload`, { method: "POST" }),
  cancelJob: (jobId: number) =>
    request<JobRecord>(`/jobs/${jobId}/cancel`, { method: "POST" }),
  startJob: (jobId: number) =>
    request<JobRecord>(`/jobs/${jobId}/start`, { method: "POST" }),
  deleteJob: (jobId: number) =>
    request<{ ok: boolean }>(`/jobs/${jobId}`, { method: "DELETE" }),
  batchStartJobs: (jobIds: number[]) =>
    request<JobRecord[]>("/jobs/batch/start", {
      method: "POST",
      body: JSON.stringify({ job_ids: jobIds }),
    }),
  batchCancelJobs: (jobIds: number[]) =>
    request<JobRecord[]>("/jobs/batch/cancel", {
      method: "POST",
      body: JSON.stringify({ job_ids: jobIds }),
    }),
};
