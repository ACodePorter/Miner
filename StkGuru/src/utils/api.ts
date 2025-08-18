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

// For APIs that return data directly (most of our backend APIs)
export interface DirectApiResponse<T> extends ApiResponse<T> {
  // The actual data is in the response itself, not in a 'data' property
}

export interface MarketDataResponse<T> {
  symbol?: string;
  interval?: string;
  bars?: T[];
  error?: string;
}

export interface QuoteData {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  timestamp: string;
}

export interface BarData {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
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

// Updated API endpoints using v1 structure
export const marketDataApi = {
  // Real-time quote data
  async getRealtimeQuote(symbol: string): Promise<QuoteData | null> {
    const response = await api.get<QuoteData>(`/api/v1/market-data/realtime/quote/${symbol}`);
    if (response.error) {
      console.error('Error fetching realtime quote:', response.error);
      return null;
    }
    return response.data || null;
  },

  // Bar data for charts
  async getBars(symbol: string, interval: string = '1d', period: string = '1d'): Promise<MarketDataResponse<BarData> | null> {
    const params = new URLSearchParams({ period });
    const response = await api.get<MarketDataResponse<BarData>>(`/api/v1/market-data/bars/${symbol}/${interval}?${params}`);
    if (response.error) {
      console.error('Error fetching bars:', response.error);
      return null;
    }
    return response.data || null;
  },
};

export const dataApi = {
  // Market breadth score
  async getMarketBreadth(marketIndex: string = 'spx', startDate?: string, endDate?: string): Promise<any[]> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    const response = await api.get<any[]>(`/api/v1/data/mbs/${marketIndex}.json?${params}`);
    if (response.error) {
      console.error('Error fetching market breadth:', response.error);
      return [];
    }
    // Backend returns data directly, not wrapped in response.data
    // Check if response has error property (backend error format)
    if (response && typeof response === 'object' && 'error' in response) {
      console.error('Backend error:', response.error);
      return [];
    }
    return response as any[];
  },

  // Market PE data
  async getMarketPE(index: string = 'spx', startDate?: string, endDate?: string): Promise<any> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    console.log('getMarketPE: Fetching from:', `/api/v1/data/market_pe/${index}.json?${params}`);
    const response = await api.get<any>(`/api/v1/data/market_pe/${index}.json?${params}`);
    console.log('getMarketPE: Raw response:', response);
    
    if (response.error) {
      console.error('Error fetching market PE:', response.error);
      return null;
    }
    // Backend returns data directly, not wrapped in response.data
    // Check if response has error property (backend error format)
    if (response && typeof response === 'object' && 'error' in response) {
      console.error('Backend error:', response.error);
      return null;
    }
    console.log('getMarketPE: Returning data:', response);
    return response;
  },

  // Wedge pop data
  async getWedgePopLatest(): Promise<any> {
    const response = await api.get<any>('/api/v1/data/wedge_pop/latest.json');
    if (response.error) {
      console.error('Error fetching wedge pop latest:', response.error);
      return null;
    }
    // Backend returns data directly, not wrapped in response.data
    return response;
  },

  async getWedgePopWedges(): Promise<any> {
    const response = await api.get<any>('/api/v1/data/wedge_pop/wedges.json');
    if (response.error) {
      console.error('Error fetching wedge pop wedges:', response.error);
      return null;
    }
    // Backend returns data directly, not wrapped in response.data
    return response;
  },

  async getWedgePopStats(startDate?: string, endDate?: string): Promise<any> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    const response = await api.get<any>(`/api/v1/data/wedge_pop/stats.json?${params}`);
    if (response.error) {
      console.error('Error fetching wedge pop stats:', response.error);
      return null;
    }
    // Backend returns data directly, not wrapped in response.data
    return response;
  },

  // OHLCVW data
  async getOHLCVW(ticker: string, startDate?: string, endDate?: string, interval: string = '1d'): Promise<any[]> {
    const params = new URLSearchParams({ interval });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    const response = await api.get<any[]>(`/api/v1/data/ohlcvw/${ticker}.json?${params}`);
    if (response.error) {
      console.error('Error fetching OHLCVW:', response.error);
      return [];
    }
    // Backend returns data directly, not wrapped in response.data
    return response as any[];
  },
};

export const watchlistApi = {
  async getWatchlist(): Promise<WatchlistItem[]> {
    const response = await api.get<{ watchlist: WatchlistItem[] }>('/api/v1/watchlist');
    return response.watchlist || [];
  },

  async addToWatchlist(ticker: string): Promise<ApiResponse<any>> {
    const qs = encodeURIComponent(ticker);
    return await api.post(`/api/v1/watchlist?ticker=${qs}`, {});
  },

  async removeFromWatchlist(ticker: string): Promise<ApiResponse<any>> {
    return await api.delete(`/api/v1/watchlist/${ticker}`);
  },
};

export const websocketApi = {
  async getStatus(): Promise<any> {
    const response = await api.get<any>('/api/v1/websocket/status');
    if (response.error) {
      console.error('Error fetching WebSocket status:', response.error);
      return null;
    }
    return response.data || null;
  },

  async getConnections(): Promise<any> {
    const response = await api.get<any>('/api/v1/websocket/connections');
    if (response.error) {
      console.error('Error fetching WebSocket connections:', response.error);
      return null;
    }
    return response.data || null;
  },

  async getRooms(): Promise<any> {
    const response = await api.get<any>('/api/v1/websocket/rooms');
    if (response.error) {
      console.error('Error fetching WebSocket rooms:', response.error);
      return null;
    }
    return response.data || null;
  },
};

export const tasksApi = {
  async updateUSTradeCalendar(): Promise<string> {
    const response = await api.get<string>('/api/v1/tasks/update_us_trade_calendar');
    return response.data || 'FAILED';
  },

  async updateSPXTickersInfo(): Promise<string> {
    const response = await api.get<string>('/api/v1/tasks/update_spx_tickers_info');
    return response.data || 'FAILED';
  },

  async updateMarketPE(): Promise<string> {
    const response = await api.get<string>('/api/v1/tasks/update_market_pe');
    return response.data || 'FAILED';
  },

  async updateSPXMarketBreadth(): Promise<string> {
    const response = await api.get<string>('/api/v1/tasks/update_spx_market_breadth');
    return response.data || 'FAILED';
  },
};
