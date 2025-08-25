import { config } from '../config/environment';

export interface QuotePayload {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  timestamp: string;
}

export interface BarsPayload {
  symbol: string;
  interval: string;
  bars: Array<{
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
  is_snapshot: boolean;
}

interface QuoteDataCandidate {
  symbol: string;
  price: number;
  change?: number;
  changePercent?: number;
  volume?: number;
  timestamp?: string;
}

interface BarsDataCandidate {
  symbol: string;
  interval: string;
  bars: Array<{
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
  is_snapshot?: boolean;
}

interface RoomMessage {
  type: 'connected' | 'room_joined' | 'room_left' | 'client_rooms' | 'subscribed' | 'bars_subscribed' | 'unsubscribed' | 'bars_unsubscribed' | 'bars' | 'quote' | 'quote_update' | 'bar_update' | 'pong' | 'error';
  message?: string;
  room_id?: string;
  success?: boolean;
  rooms?: string[];
  symbol?: string;
  interval?: string;
  timestamp: string;
  data?: QuoteDataCandidate | BarUpdateDataCandidate | BarsDataCandidate;
}

interface BarUpdateDataCandidate {
  symbol: string;
  interval: string;
  bar: {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  };
}

class WebSocketClient {
  private ws: WebSocket | null = null;
  private isConnecting = false;
  private clientId: string;
  private subscriptions = new Map<string, (data: QuotePayload) => void>();
  private barsSubscriptions = new Map<string, (data: BarsPayload) => void>();
  private connectedRooms = new Set<string>();
  private baseUrl: string;
  
  // Event callbacks for room state changes
  private roomStateChangeCallbacks = new Set<() => void>();
  
  // Reconnection settings
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private reconnectTimer: NodeJS.Timeout | null = null;
  private shouldReconnect = true;
  private connectionStartTime = Date.now();
  private lastConnectionStatus: 'disconnected' | 'connecting' | 'connected' | 'disconnecting' = 'disconnected';
  private isDisconnecting = false;

  constructor() {
    // Use environment configuration to determine WebSocket URL
    // For development, use ws://localhost:80 (backend runs on port 80 via nginx)
    // For production, use wss:// with the configured domain
    if (config.isDevelopment || config.isTest) {
      this.baseUrl = 'ws://localhost:80';
    } else {
      // Convert HTTP to WebSocket protocol
      const wsUrl = config.apiBaseUrl.replace(/^http/, 'ws');
      this.baseUrl = wsUrl;
    }
    
    this.clientId = `client-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    this.connect();
  }

  // Add callback for room state changes
  onRoomStateChange(callback: () => void): () => void {
    this.roomStateChangeCallbacks.add(callback);
    return () => {
      this.roomStateChangeCallbacks.delete(callback);
    };
  }

  // Notify all room state change callbacks
  private notifyRoomStateChange() {
    this.roomStateChangeCallbacks.forEach(callback => {
      try {
        callback();
      } catch (error) {
        console.error('Error in room state change callback:', error);
      }
    });
  }

  private connect() {
    if (this.isConnecting || this.ws?.readyState === WebSocket.OPEN) return;
    
    this.isConnecting = true;
    this.lastConnectionStatus = 'connecting';
    this.notifyRoomStateChange(); // Notify status change
    
    const wsUrl = `${this.baseUrl}/ws/${this.clientId}`;
    
    try {

      this.ws = new WebSocket(wsUrl);
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);
    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.isConnecting = false;
      this.lastConnectionStatus = 'disconnected';
      this.notifyRoomStateChange(); // Notify status change
      this.scheduleReconnect();
    }
  }

  private handleOpen() {

    this.isConnecting = false;
    this.isDisconnecting = false;
    this.reconnectAttempts = 0; // Reset reconnect attempts on successful connection
    this.lastConnectionStatus = 'connected';
    this.notifyRoomStateChange(); // Notify status change
    
    // Re-subscribe to all active subscriptions
    this.resubscribeAll();
  }

  private handleMessage(event: MessageEvent) {
    try {
      const data: RoomMessage = JSON.parse(event.data);

      
      switch (data.type) {
        case 'connected':

          break;
          
        case 'room_joined':
          if (data.room_id && data.success) {
            this.connectedRooms.add(data.room_id);

            this.notifyRoomStateChange(); // Notify listeners
          }
          break;
          
        case 'room_left':
          if (data.room_id) {  // Remove the success check since backend doesn't send it
            this.connectedRooms.delete(data.room_id);
            this.notifyRoomStateChange(); // Notify listeners
          }
          break;
          
        case 'subscribed':
          if (data.room_id && data.symbol) {
            this.connectedRooms.add(data.room_id);
            console.log(`Joined room ${data.room_id} for symbol ${data.symbol}`);
            this.notifyRoomStateChange(); // Notify listeners
          }
          break;
          
        case 'bars_subscribed':
          if (data.room_id && data.symbol && data.interval) {
            this.connectedRooms.add(data.room_id);
            this.notifyRoomStateChange(); // Notify listeners
          }
          break;
          
        case 'unsubscribed':
          // Handle quote unsubscription confirmation
          if (data.symbol) {
            const roomId = `quotes:${data.symbol.toUpperCase()}`;
            this.connectedRooms.delete(roomId);
            console.log(`Unsubscribed from quotes for ${data.symbol}, removed room: ${roomId}`);
            this.notifyRoomStateChange(); // Notify listeners
          }
          break;
          
        case 'bars_unsubscribed':
          // Handle bars unsubscription confirmation
          if (data.symbol && data.interval) {
            const roomId = `bars:${data.symbol.toUpperCase()}:${data.interval}`;
            this.connectedRooms.delete(roomId);
            console.log(`Unsubscribed from bars for ${data.symbol}:${data.interval}, removed room: ${roomId}`);
            this.notifyRoomStateChange(); // Notify listeners
          }
          break;
          
        case 'quote_update':
          // Handle real-time quote updates from room broadcasting
          if (data.data && this.isQuoteData(data.data)) {
            this.handleQuoteUpdate(data.data);
          }
          break;
          
        case 'quote':
          // Handle quote messages (direct from backend)
          console.log('WebSocket received quote message:', data);
          console.log('Current connected rooms:', Array.from(this.connectedRooms));
          if (data.data && this.isQuoteData(data.data)) {
            console.log('Quote data validation passed, calling handleQuoteUpdate');
            this.handleQuoteUpdate(data.data);
          } else {
            console.log('Quote data validation failed:', data.data);
            console.log('isQuoteData result:', this.isQuoteData(data.data));
          }
          break;
          
        case 'bars':
          // Handle bars data (initial snapshot or updates)
          console.log('WebSocket received bars message:', data);
          if (data.data && this.isBarsData(data.data)) {
            console.log('Bars data validation passed, calling handleBarsData');
            this.handleBarsData(data.data);
          } else {
            console.log('Bars data validation failed:', data.data);
            console.log('isBarsData result:', this.isBarsData(data.data));
          }
          break;
          
        case 'bar_update':
          // Handle real-time bar updates from room broadcasting
          if (data.data && this.isBarUpdateData(data.data)) {
            this.handleBarUpdate(data.data);
          }
          break;
          
        case 'pong':
          // Handle ping/pong for connection health
          break;
          
        case 'error':
          console.error('WebSocket error:', data.message);
          break;
          
        default:
          // Handle legacy market data updates (quotes and bars)
          this.handleMarketData(data);
          break;
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }

  private handleMarketData(data: unknown) {
    // Type guard for quote data
    if (this.isQuoteData(data)) {
      const quoteData: QuotePayload = {
        symbol: data.symbol,
        price: data.price,
        change: data.change || 0,
        changePercent: data.changePercent || 0,
        volume: data.volume || 0,
        timestamp: data.timestamp || new Date().toISOString()
      };
      
      // Emit to specific symbol subscribers
      const symbol = data.symbol.toUpperCase();
      if (this.subscriptions.has(symbol)) {
        this.subscriptions.get(symbol)!(quoteData);
      }
    }
    
    // Type guard for bars data
    if (this.isBarsData(data)) {
      const barsData: BarsPayload = {
        symbol: data.symbol,
        interval: data.interval,
        bars: data.bars,
        is_snapshot: data.is_snapshot || false
      };
      
      // Emit to specific bars subscribers
      const key = `${data.symbol.toUpperCase()}:${data.interval}`;
      if (this.barsSubscriptions.has(key)) {
        this.barsSubscriptions.get(key)!(barsData);
      }
    }
  }

  private handleQuoteUpdate(quoteData: QuoteDataCandidate) {
    // Handle quote updates from room broadcasting
    const formattedQuote: QuotePayload = {
      symbol: quoteData.symbol,
      price: quoteData.price,
      change: quoteData.change || 0,
      changePercent: quoteData.changePercent || 0,
      volume: typeof quoteData.volume === 'string' ? parseInt(quoteData.volume, 10) || 0 : (quoteData.volume || 0),
      timestamp: quoteData.timestamp || new Date().toISOString()
    };
    
    console.log(`Processing quote update for ${quoteData.symbol}:`, formattedQuote);
    
    // Emit to specific symbol subscribers
    const symbol = quoteData.symbol.toUpperCase();
    if (this.subscriptions.has(symbol)) {
      console.log(`Emitting quote to subscription for ${symbol}`);
      this.subscriptions.get(symbol)!(formattedQuote);
    } else {
      console.log(`No subscription found for ${symbol}. Available subscriptions:`, Array.from(this.subscriptions.keys()));
    }
  }

  private handleBarsData(barsData: BarsDataCandidate) {
    // Handle bars data (initial snapshot or updates)
    console.log('handleBarsData called with:', barsData);
    
    const formattedBars: BarsPayload = {
      symbol: barsData.symbol,
      interval: barsData.interval,
      bars: barsData.bars,
      is_snapshot: barsData.is_snapshot || false
    };
    
    console.log('Formatted bars payload:', formattedBars);
    
    // Emit to specific bars subscribers
    const key = `${barsData.symbol.toUpperCase()}:${barsData.interval}`;
    console.log('Looking for bars subscription with key:', key);
    console.log('Available bars subscriptions:', Array.from(this.barsSubscriptions.keys()));
    
    if (this.barsSubscriptions.has(key)) {
      console.log('Found bars subscription, emitting data');
      this.barsSubscriptions.get(key)!(formattedBars);
    } else {
      console.log('No bars subscription found for key:', key);
    }
  }

  private handleBarUpdate(barData: BarUpdateDataCandidate) {
    // Handle bar updates from room broadcasting
    const formattedBars: BarsPayload = {
      symbol: barData.symbol,
      interval: barData.interval,
      bars: [barData.bar], // Convert single bar to array for compatibility
      is_snapshot: false
    };
    
    // Emit to specific bars subscribers
    const key = `${barData.symbol.toUpperCase()}:${barData.interval}`;
    if (this.barsSubscriptions.has(key)) {
      this.barsSubscriptions.get(key)!(formattedBars);
    }
  }

  private isQuoteData(data: unknown): data is QuoteDataCandidate {
    if (typeof data !== 'object' || data === null) return false;
    const candidate = data as Record<string, unknown>;
    
    // Check required fields
    if (typeof candidate.symbol !== 'string' || typeof candidate.price !== 'number') {
      return false;
    }
    
    // Optional fields can be string or number (backend sends volume as string)
    if (candidate.change !== undefined && typeof candidate.change !== 'number') {
      return false;
    }
    if (candidate.changePercent !== undefined && typeof candidate.changePercent !== 'number') {
      return false;
    }
    if (candidate.volume !== undefined && typeof candidate.volume !== 'number' && typeof candidate.volume !== 'string') {
      return false;
    }
    if (candidate.timestamp !== undefined && typeof candidate.timestamp !== 'string') {
      return false;
    }
    
    return true;
  }

  private isBarsData(data: unknown): data is BarsDataCandidate {
    if (typeof data !== 'object' || data === null) return false;
    
    const candidate = data as Record<string, unknown>;
    if (typeof candidate.symbol !== 'string' || typeof candidate.interval !== 'string' || !Array.isArray(candidate.bars)) {
      return false;
    }
    
    // Validate that each bar has the required properties
    return candidate.bars.every((bar: unknown) => {
      if (typeof bar !== 'object' || bar === null) return false;
      const barCandidate = bar as Record<string, unknown>;
      return typeof barCandidate.timestamp === 'number' && 
             typeof barCandidate.open === 'number' && 
             typeof barCandidate.high === 'number' && 
             typeof barCandidate.low === 'number' && 
             typeof barCandidate.close === 'number' && 
             typeof barCandidate.volume === 'number';
    });
  }

  private isBarUpdateData(data: unknown): data is { symbol: string; interval: string; bar: {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  } } {
    if (typeof data !== 'object' || data === null) return false;
    const candidate = data as Record<string, unknown>;
    return typeof candidate.symbol === 'string' && 
           typeof candidate.interval === 'string' && 
           typeof candidate.bar === 'object' && 
           candidate.bar !== null && 
           typeof (candidate.bar as Record<string, unknown>).timestamp === 'number' && 
           typeof (candidate.bar as Record<string, unknown>).open === 'number' && 
           typeof (candidate.bar as Record<string, unknown>).high === 'number' && 
           typeof (candidate.bar as Record<string, unknown>).low === 'number' && 
           typeof (candidate.bar as Record<string, unknown>).close === 'number' && 
           typeof (candidate.bar as Record<string, unknown>).volume === 'number';
  }

  private handleClose(_event: CloseEvent) {

    this.isConnecting = false;
    this.isDisconnecting = false;
    this.lastConnectionStatus = 'disconnected';
    this.notifyRoomStateChange(); // Notify status change
    
    // Clear local room tracking but keep subscriptions for reconnection
    this.connectedRooms.clear();
    
    // Schedule reconnection if enabled
    if (this.shouldReconnect) {
      this.scheduleReconnect();
    }
  }

  private handleError(error: Event) {
    console.error('WebSocket error:', error);
    if (!this.isDisconnecting) {
      this.lastConnectionStatus = 'disconnected';
      this.notifyRoomStateChange(); // Notify status change
      
      // Also try to reconnect on error if not already reconnecting
      if (this.shouldReconnect && !this.reconnectTimer) {
        this.scheduleReconnect();
      }
    }
  }

  // Method to gracefully disconnect
  disconnect() {
    this.isDisconnecting = true;
    this.lastConnectionStatus = 'disconnecting';
    this.shouldReconnect = false; // Stop automatic reconnection
    this.notifyRoomStateChange(); // Notify status change
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect');
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) {
      return;
    }
    
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.shouldReconnect = false;
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000); // Exponential backoff, max 30s
    
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.shouldReconnect) {
        this.connect();
      }
    }, delay);
  }

  private resubscribeAll() {
    let restoredCount = 0;
    
    // Re-subscribe to all active subscriptions
    this.subscriptions.forEach((_callback, symbol) => {
      try {
        this.subscribeToQuotes(symbol);
        restoredCount++;
      } catch (error) {
        console.error(`❌ Failed to re-subscribe to quotes for ${symbol}:`, error);
      }
    });
    
    this.barsSubscriptions.forEach((_callback, key) => {
      const [symbol, interval] = key.split(':');
      if (symbol && interval) {
        try {
          this.subscribeToBars(symbol, interval);
          restoredCount++;
        } catch (error) {
          console.error(`❌ Failed to re-subscribe to bars for ${symbol}:${interval}:`, error);
        }
      }
    });
    
    // Notify components that subscriptions have been restored
    setTimeout(() => {
      this.notifyRoomStateChange();
    }, 100); // Small delay to ensure backend has processed subscriptions
  }

  // Subscribe to quotes
  subscribe(symbol: string, callback: (data: QuotePayload) => void): () => void {
    const upperSymbol = symbol.toUpperCase();
    
    // Store the subscription
    this.subscriptions.set(upperSymbol, callback);
    
    // Subscribe if connected
    if (this.isReady()) {
      this.subscribeToQuotes(upperSymbol);
    }
    
    // Return unsubscribe function
    const unsubscribeFn = () => {
      this.subscriptions.delete(upperSymbol);
      this.unsubscribeFromQuotes(upperSymbol);
      
      // 🔥 Notify room state change after subscription removal
      this.notifyRoomStateChange();
    };
    
    return unsubscribeFn;
  }

  // Subscribe to bars
  subscribeBars(symbol: string, interval: string, callback: (data: BarsPayload) => void): () => void {
    const upperSymbol = symbol.toUpperCase();
    const key = `${upperSymbol}:${interval}`;
    
    // Store the subscription
    this.barsSubscriptions.set(key, callback);
    
    // Subscribe if connected
    if (this.isReady()) {
      this.subscribeToBars(upperSymbol, interval);
    }
    
    // Return unsubscribe function
    return () => {
      this.barsSubscriptions.delete(key);
      this.unsubscribeFromBars(upperSymbol, interval);
    };
  }

  private subscribeToQuotes(symbol: string) {
    if (!this.isReady()) {
      return;
    }
    
    const message = {
      type: 'subscribe',
      symbol: symbol
    };
    
    try {
      this.ws?.send(JSON.stringify(message));
    } catch (error) {
      console.error(`❌ Error sending subscribe message for ${symbol}:`, error);
    }
  }

  private subscribeToBars(symbol: string, interval: string) {
    if (!this.isReady()) return;
    
    const message = {
      type: 'subscribe_bars',
      symbol: symbol,
      interval: interval
    };
    
    this.ws?.send(JSON.stringify(message));
  }

  private unsubscribeFromQuotes(symbol: string) {
    // Send unsubscribe message to backend
    if (!this.isReady()) {
      console.log(`WebSocket not ready, cannot unsubscribe from quotes: ${symbol}`);
      return;
    }
    
    const message = {
      type: 'unsubscribe',
      symbol: symbol
    };
    
    try {
      this.ws?.send(JSON.stringify(message));
      console.log(`Sent unsubscribe message for quotes: ${symbol}`);
      
      // Remove from local subscriptions immediately
      this.subscriptions.delete(symbol.toUpperCase());
      console.log(`Removed quote subscription for: ${symbol}`);
    } catch (error) {
      console.error(`❌ Error sending unsubscribe message for ${symbol}:`, error);
    }
  }

  private unsubscribeFromBars(symbol: string, interval: string) {
    // Send unsubscribe_bars message to backend
    if (!this.isReady()) {
      console.log(`WebSocket not ready, cannot unsubscribe from bars: ${symbol}:${interval}`);
      return;
    }
    
    const message = {
      type: 'unsubscribe_bars',
      symbol: symbol,
      interval: interval
    };
    
    try {
      this.ws?.send(JSON.stringify(message));
      console.log(`Sent unsubscribe_bars message for: ${symbol}:${interval}`);
      
      // Remove from local subscriptions immediately
      const key = `${symbol.toUpperCase()}:${interval}`;
      this.barsSubscriptions.delete(key);
      console.log(`Removed bars subscription for: ${key}`);
    } catch (error) {
      console.error(`❌ Error sending unsubscribe_bars message for ${symbol}:${interval}:`, error);
    }
  }

  // leaveRoom method removed - now using proper unsubscribe messages

  // Check if WebSocket is ready
  isReady(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // Get connection status
  getStatus(): 'disconnected' | 'connecting' | 'connected' | 'disconnecting' {
    if (this.isDisconnecting) return 'disconnecting';
    if (this.isConnecting) return 'connecting';
    if (this.isReady()) return 'connected';
    if (this.reconnectTimer && this.shouldReconnect) return 'connecting'; // Show connecting during reconnection attempts
    if (this.ws?.readyState === WebSocket.CLOSED) return 'disconnected';
    return this.lastConnectionStatus;
  }

  // Get detailed connection status
  getDetailedStatus() {
    return {
      status: this.getStatus(),
      isConnecting: this.isConnecting,
      isDisconnecting: this.isDisconnecting,
      isReady: this.isReady(),
      reconnectAttempts: this.reconnectAttempts,
      maxReconnectAttempts: this.maxReconnectAttempts,
      shouldReconnect: this.shouldReconnect,
      lastConnectionStatus: this.lastConnectionStatus,
      connectionStartTime: this.connectionStartTime,
      uptime: this.isReady() ? Date.now() - this.connectionStartTime : 0
    };
  }

  // Get connected rooms
  getConnectedRooms(): string[] {
    return Array.from(this.connectedRooms);
  }

  // Manually trigger room state change notification (for testing)
  triggerRoomStateChange() {
    this.notifyRoomStateChange();
  }

  // Manually trigger reconnection
  triggerReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
    this.shouldReconnect = true;
    this.connect();
  }

  // Check reconnection state and force if needed
  checkAndForceReconnect() {
    if (this.getStatus() === 'disconnected' && this.shouldReconnect && !this.reconnectTimer) {
      this.scheduleReconnect();
    } else if (this.getStatus() === 'disconnected' && !this.shouldReconnect) {
      this.shouldReconnect = true;
      this.reconnectAttempts = 0;
      this.scheduleReconnect();
    }
  }

  // Reset reconnection settings
  resetReconnection() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
    this.shouldReconnect = true;
  }

  // Manually sync all subscriptions
  syncSubscriptions() {
    if (this.isReady()) {
      this.resubscribeAll();
    }
  }

  // Get current room state for debugging
  getRoomStateDebug() {
    return {
      connectedRooms: Array.from(this.connectedRooms),
      totalRooms: this.connectedRooms.size,
      subscriptions: Array.from(this.subscriptions.keys()),
      totalSubscriptions: this.subscriptions.size,
      barsSubscriptions: Array.from(this.barsSubscriptions.keys()),
      totalBarsSubscriptions: this.barsSubscriptions.size,
      connectionStatus: this.getDetailedStatus()
    };
  }
}

// Create singleton instance
export const wsClient = new WebSocketClient();