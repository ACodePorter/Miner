import { apiConfig } from '../config/environment';

export interface WatchlistItem {
  ticker: string;
  added_at: string;
}

export interface ApiResponse<T> {
  status?: string;
  message?: string;
  error?: string;
  data?: T;
  watchlist?: WatchlistItem[];
}

export const api = {
  async get<T>(endpoint: string): Promise<ApiResponse<T>> {
    try {
      const url = apiConfig.getApiUrl(endpoint);
      const response = await fetch(url);
      return await response.json();
    } catch (error) {
      return { error: error instanceof Error ? error.message : 'Unknown error' };
    }
  },

  async post<T>(endpoint: string, data: any): Promise<ApiResponse<T>> {
    try {
      const url = apiConfig.getApiUrl(endpoint);
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      return await response.json();
    } catch (error) {
      return { error: error instanceof Error ? error.message : 'Unknown error' };
    }
  },

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    try {
      const url = apiConfig.getApiUrl(endpoint);
      const response = await fetch(url, {
        method: 'DELETE',
      });
      return await response.json();
    } catch (error) {
      return { error: error instanceof Error ? error.message : 'Unknown error' };
    }
  },
};

export const watchlistApi = {
  async getWatchlist(): Promise<WatchlistItem[]> {
    const response = await api.get<{ watchlist: WatchlistItem[] }>('/api/watchlist');
    return response.watchlist || [];
  },

  async addToWatchlist(ticker: string): Promise<ApiResponse<any>> {
    const qs = encodeURIComponent(ticker);
    return await api.post(`/api/watchlist?ticker=${qs}`, {});
  },

  async removeFromWatchlist(ticker: string): Promise<ApiResponse<any>> {
    return await api.delete(`/api/watchlist/${ticker}`);
  },
};
