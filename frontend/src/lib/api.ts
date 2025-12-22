import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
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
};

export const documentsApi = {
  list: (page = 1, pageSize = 20, status?: string) =>
    api.get('/api/documents/', { params: { page, page_size: pageSize, status } }),

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
};

export const adminApi = {
  qualityReport: () =>
    api.get('/api/admin/quality/report'),

  failedDocuments: () =>
    api.get('/api/admin/documents/failed'),

  retryDocument: (id: string) =>
    api.post(`/api/admin/documents/${id}/retry`),
};
