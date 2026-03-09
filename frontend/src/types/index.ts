export type JobSourceType = "qb_auto" | "qb_manual" | "folder_manual";
export type JobStatus =
  | "imported"
  | "pending"
  | "packing"
  | "packed"
  | "copying_to_mount"
  | "waiting_for_clouddrive_task"
  | "uploading"
  | "completed"
  | "failed"
  | "cancelled";

export interface JobRecord {
  id: number;
  source_type: JobSourceType;
  source_key: string;
  source_fingerprint: string;
  torrent_hash?: string | null;
  torrent_name: string;
  source_path: string;
  category?: string | null;
  tags: string[];
  auto_upload: boolean;
  status: JobStatus;
  iso_path?: string | null;
  iso_size_bytes?: number | null;
  upload_target_path?: string | null;
  clouddrive_task_key?: string | null;
  upload_bytes?: number | null;
  upload_total_bytes?: number | null;
  pack_progress_percent?: number | null;
  manual_repack: boolean;
  manual_reupload: boolean;
  pack_log?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EventRecord {
  id: number;
  job_id?: number | null;
  level: string;
  message: string;
  created_at: string;
}

export interface SystemStatus {
  app_name: string;
  qbittorrent_connected: boolean;
  clouddrive_connected: boolean;
  xorriso_available: boolean;
  degraded_upload_monitoring: boolean;
  active_uploads: number;
  queued_jobs: number;
  auto_polling_enabled: boolean;
  auto_import_mode: string;
}

export interface QBTaskSummary {
  torrent_hash: string;
  name: string;
  source_path: string;
  category?: string | null;
  tags: string[];
  completed_at: string;
  already_known: boolean;
}

export interface SettingsModel {
  log_level: string;
  qbittorrent_url: string;
  qbittorrent_username: string;
  qbittorrent_password: string;
  qbittorrent_poll_interval_seconds: number;
  qbittorrent_category_filter: string;
  qbittorrent_tag_filter: string;
  clouddrive_url: string;
  clouddrive_upload_bandwidth_mb: number;
  clouddrive_username: string;
  clouddrive_password: string;
  clouddrive_target_path: string;
  auto_import_mode: string;
}
