import axios from 'axios';
import { parseSSE } from './sse';
import type { SSEEvent } from './sse';

const API_BASE = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? '' : 'http://localhost:8000');

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,  // Include cookies for session auth
});

// Add API key to requests
api.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem('api_key');
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

// API functions
export const queryApi = {
  ask: (query: string, limit = 5) =>
    api.post('/api/query/', { query, limit }),

  search: (query: string, limit = 10) =>
    api.post('/api/search/', { query, limit }),

  streamAsk: async (
    query: string,
    onEvent: (event: SSEEvent) => void,
    maxIterations = 3
  ): Promise<void> => {
    const apiKey = localStorage.getItem('api_key');

    const response = await fetch(`${API_BASE}/api/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      },
      credentials: 'include',
      body: JSON.stringify({ query, max_iterations: maxIterations }),
    });

    if (!response.ok) {
      throw new Error(`Stream request failed: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value, { stream: true });
      const events = parseSSE(text);

      for (const event of events) {
        onEvent(event);
      }
    }
  },
};

export const documentsApi = {
  list: (params?: { page?: number; pageSize?: number; status?: string; needsReview?: boolean; search?: string; sortBy?: string; sortOrder?: string }) =>
    api.get('/api/documents/', {
      params: {
        page: params?.page || 1,
        page_size: params?.pageSize || 20,
        status: params?.status,
        needs_review: params?.needsReview,
        search: params?.search,
        sort_by: params?.sortBy,
        sort_order: params?.sortOrder,
      },
    }),

  get: (id: string) =>
    api.get(`/api/documents/${id}`),

  create: (url: string) =>
    api.post('/api/documents/', { url }),

  uploadPdf: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/api/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  delete: (id: string) =>
    api.delete(`/api/documents/${id}`),

  update: (id: string, data: { title?: string; author?: string }) =>
    api.put(`/api/documents/${id}`, data),

  reprocess: (id: string) =>
    api.post(`/api/documents/${id}/reprocess`),

  markReviewed: (id: string) =>
    api.post(`/api/documents/${id}/review`),
};

export const adminApi = {
  qualityReport: () =>
    api.get('/api/admin/quality/report'),

  failedDocuments: () =>
    api.get('/api/admin/documents/failed'),

  retryDocument: (id: string) =>
    api.post(`/api/admin/documents/${id}/retry`),
};

export const jobsApi = {
  list: (params?: { status?: string; jobType?: string; search?: string; sortBy?: string; sortOrder?: string; page?: number; pageSize?: number }) =>
    api.get('/api/admin/jobs', {
      params: {
        status: params?.status,
        job_type: params?.jobType,
        search: params?.search,
        sort_by: params?.sortBy,
        sort_order: params?.sortOrder,
        page: params?.page || 1,
        page_size: params?.pageSize || 50,
      },
    }),

  getStats: () =>
    api.get('/api/admin/jobs/stats'),

  getJob: (id: string) =>
    api.get(`/api/admin/jobs/${id}`),

  retry: (id: string) =>
    api.post(`/api/admin/jobs/${id}/retry`),

  bulkRetry: () =>
    api.post('/api/admin/jobs/bulk-retry'),

  createBatch: (urls: string[]) =>
    api.post('/api/admin/jobs/batch', { urls }),
};

export const driveApi = {
  getServiceAccount: () =>
    api.get('/api/admin/drive/service-account'),

  listFolders: () =>
    api.get('/api/admin/drive/folders'),

  createFolder: (googleFolderId: string, name?: string) =>
    api.post('/api/admin/drive/folders', { google_folder_id: googleFolderId, name }),

  syncFolder: (id: string, processFiles: boolean = true) =>
    api.post(`/api/admin/drive/folders/${id}/sync`, null, { params: { process_files: processFiles } }),

  listFiles: (folderId: string, status?: string) =>
    api.get(`/api/admin/drive/folders/${folderId}/files`, { params: { status } }),

  deleteFolder: (id: string) =>
    api.delete(`/api/admin/drive/folders/${id}`),
};
