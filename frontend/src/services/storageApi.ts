import axios from "axios";
import { http, resolveApiUrl } from "./http";
import type { ApiEnvelope } from "../types/api";

export interface StoragePresignPayload {
  taskId: string;
  kind: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
  sha256: string;
  role?: string;
  sortOrder?: number;
}

export interface StoragePresignResult {
  file_id: string;
  task_id: string;
  cos_key: string;
  upload_url: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_in: number;
}

export interface FileDownloadUrlResult {
  file_id: string;
  source_type: "asset" | "result";
  task_id: string;
  cos_key: string;
  download_url: string;
  expires_in: number;
}

export async function createStoragePresign(payload: StoragePresignPayload): Promise<StoragePresignResult> {
  const resp = await http.post<ApiEnvelope<StoragePresignResult>>("/v1/storage/presign", {
    task_id: payload.taskId,
    kind: payload.kind,
    file_name: payload.fileName,
    mime_type: payload.mimeType,
    size_bytes: payload.sizeBytes,
    sha256: payload.sha256,
    role: payload.role ?? "upload",
    sort_order: payload.sortOrder ?? 0,
  });
  return resp.data.data;
}

export async function uploadFileToPresignedUrl(file: File, presign: StoragePresignResult): Promise<void> {
  await axios.put(presign.upload_url, file, {
    headers: {
      ...presign.headers,
      "Content-Type": presign.headers["Content-Type"] ?? file.type,
    },
  });
}

export async function fetchFileDownloadUrl(fileId: string): Promise<FileDownloadUrlResult> {
  const resp = await http.get<ApiEnvelope<FileDownloadUrlResult>>(`/v1/files/${fileId}/download-url`);
  return {
    ...resp.data.data,
    download_url: resolveApiUrl(resp.data.data.download_url),
  };
}

export async function calculateFileSha256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}
