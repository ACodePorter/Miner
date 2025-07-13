import { useQuery } from '@tanstack/react-query';

interface PEData {
  index: string;
  data: [number, number][];
  stats: {
    avg_20y: number;
    current_pe: number;
    min_pe: number;
    max_pe: number;
  };
}

export interface SectorScore {
  sector_key: string;
  score: number;
}

export interface MarketBreadthData {
  index_name: string;
  trade_date: string;
  score_sma20: number;
  score_sma50: number;
  score_sma200: number;
  sector_score20: SectorScore[];
  sector_score50: SectorScore[];
  sector_score200: SectorScore[];
}

// Fetch PE data with caching
export const usePEData = (indexId: string) => {
  return useQuery({
    queryKey: ['market-pe', indexId],
    queryFn: async (): Promise<PEData> => {
      const response = await fetch(`/api/market_pe?index=${indexId}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch ${indexId} PE data: ${response.status}`);
      }
      return response.json();
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
    retry: 3,
    retryDelay: (attemptIndex: number) => Math.min(1000 * 2 ** attemptIndex, 30000),
    refetchOnWindowFocus: false,
    refetchOnReconnect: true,
  });
};

// Fetch market breadth data with caching
export const useMarketBreadthData = (indexId: string) => {
  return useQuery({
    queryKey: ['market-breadth', indexId],
    queryFn: async (): Promise<MarketBreadthData[]> => {
      const response = await fetch(`/api/mbs?market_index=${indexId}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const arr = await response.json();
      if (Array.isArray(arr) && arr.length > 0) {
        return arr;
      } else {
        throw new Error("No market breadth data available");
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    retry: 3,
    retryDelay: (attemptIndex: number) => Math.min(1000 * 2 ** attemptIndex, 30000),
    refetchOnWindowFocus: false,
    refetchOnReconnect: true,
  });
}; 