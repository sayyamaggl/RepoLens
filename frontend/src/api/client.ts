import axios from 'axios';
import { 
  RepoInfo, 
  OverviewResponse, 
  GraphResponse, 
  FileSummaryResponse 
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  deleteRepo: async (id: number): Promise<{ status: string; message: string }> => {
    const response = await apiClient.delete(`/repo/${id}`);
    return response.data;
  },

  analyzeRepo: async (repoUrl: string): Promise<{ repo_id: number; status: string; message: string }> => {
    const response = await apiClient.post('/analyze', { repo_url: repoUrl });
    return response.data;
  },

  getRepos: async (): Promise<{ repos: RepoInfo[]; total: number }> => {
    const response = await apiClient.get('/repos');
    return response.data;
  },

  getRepoStatus: async (id: number): Promise<RepoInfo> => {
    const response = await apiClient.get(`/repo/${id}/status`);
    return response.data;
  },

  getRepoOverview: async (id: number): Promise<OverviewResponse> => {
    const response = await apiClient.get(`/repo/${id}/overview`);
    return response.data;
  },

  getRepoGraph: async (id: number): Promise<GraphResponse> => {
    const response = await apiClient.get(`/repo/${id}/graph`);
    return response.data;
  },

  getFileSummary: async (repoId: number, fileId: number): Promise<FileSummaryResponse> => {
    const response = await apiClient.get(`/repo/${repoId}/file/${fileId}/summary`);
    return response.data;
  },

  getRepoFiles: async (id: number): Promise<{ files: any[], total: number }> => {
    const response = await apiClient.get(`/repo/${id}/files`);
    return response.data;
  }
};