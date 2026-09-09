import type { Capabilities, Cue, Project, Recording } from './types';

export function apiBase() {
  if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('practice') === '1') return 'http://127.0.0.1:8766';
  const configured = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8765';
  const url = new URL(configured);
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('For privacy, the service address must be a loopback HTTP origin. Remote servers are not supported.');
  }
  return url.origin;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, { ...init, cache: 'no-store' });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string | { msg: string }[] };
      if (typeof payload.detail === 'string') message = payload.detail;
      else if (Array.isArray(payload.detail)) message = payload.detail.map(item => item.msg).join('; ');
    } catch {
      // The status message is sufficient when the server did not return JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const studioApi = {
  capabilities: () => request<Capabilities>('/api/capabilities'),
  projects: () => request<Project[]>('/api/projects'),
  project: (projectId: string) => request<Project>(`/api/projects/${projectId}`),
  createProject: (name: string) =>
    request<Project>('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
  updateProject: (projectId: string, changes: { name?: string; reviewer?: string }) =>
    request<Project>(`/api/projects/${projectId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    }),
  importRecording: (projectId: string, form: FormData) =>
    request<Recording>(`/api/projects/${projectId}/recordings`, { method: 'POST', body: form }),
  processRecording: (recordingId: string, settings: { model: string; language: string; dual_pass: boolean }) =>
    request<{ status: string }>(`/api/recordings/${recordingId}/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    }),
  recording: (recordingId: string) => request<Recording>(`/api/recordings/${recordingId}`),
  cues: (recordingId: string) => request<Cue[]>(`/api/recordings/${recordingId}/cues`),
  updateCue: (cueId: number, changes: Partial<Pick<Cue, 'final_text' | 'speaker' | 'start_ms' | 'end_ms' | 'status'>> & { reviewer?: string; expected_revision: number }) =>
    request<Cue>(`/api/cues/${cueId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    }),
  splitCue: (cueId: number, changes: Pick<Cue, 'final_text' | 'speaker' | 'start_ms' | 'end_ms'> & { split_ms: number; reviewer?: string; expected_revision: number }) =>
    request<Cue[]>(`/api/cues/${cueId}/split`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    }),
  history: (cueId: number) => request<{ id: number; action: string; reviewer: string; created_at: string }[]>(`/api/cues/${cueId}/history`),
  mediaUrl: (recordingId: string) => `${apiBase()}/api/recordings/${recordingId}/media`,
  exportUrl: (recordingId: string, format: 'docx' | 'nvivo' | 'xlsx' | 'txt' | 'vtt' | 'srt' | 'csv' | 'json' | 'changes' | 'report') =>
    `${apiBase()}/api/recordings/${recordingId}/export/${format}`,
  bundleUrl: (projectId: string, includeMedia = false) =>
    `${apiBase()}/api/projects/${projectId}/bundle?include_media=${includeMedia ? 'true' : 'false'}`,
};
