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
  type: 'connected' | 'room_joined' | 'room_left' | 'client_rooms' | 'subscribed' | 'bars_subscribed' | 'quote_update' | 'bar_update' | 'pong' | 'error';
  message?: string;
  room_id?: string;
  success?: boolean;
  rooms?: string[];
  symbol?: string;
  interval?: string;
  timestamp: string;
  data?: QuoteDataCandidate | BarUpdateDataCandidate;
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
      console.log(`🔌 Attempting WebSocket connection to: ${wsUrl}`);
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
    console.log('WebSocket connected');
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
      console.log('📨 WebSocket message received:', data);
      
      switch (data.type) {
        case 'connected':
          console.log('✅ Connected to WebSocket service');
          break;
          
        case 'room_joined':
          if (data.room_id && data.success) {
            this.connectedRooms.add(data.room_id);
            console.log(`🚪 Joined room: ${data.room_id}`);
            console.log(`🔌 Total connected rooms: ${this.connectedRooms.size}`);
            console.log(`🔌 Connected rooms:`, Array.from(this.connectedRooms));
            this.notifyRoomStateChange(); // Notify listeners
          }
          break;
          
        case 'room_left':
          console.log(`🔍 Processing room_left message:`, data);
          if (data.room_id) {  // Remove the success check since backend doesn't send it
            console.log(`🗑️ Removing room ${data.room_id} from connectedRooms`);
            this.connectedRooms.delete(data.room_id);
            console.log(`🚪 Left room: ${data.room_id}`);
            console.log(`🔌 Total connected rooms: ${this.connectedRooms.size}`);
            console.log(`🔌 Connected rooms:`, Array.from(this.connectedRooms));
            this.notifyRoomStateChange(); // Notify listeners
            console.log(`📢 Room state change notification sent after leaving room ${data.room_id}`);
          } else {
            console.log(`⚠️ room_left message missing room_id:`, data);
          }
          break;
          
        case 'subscribed':
          if (data.room_id && data.symbol) {
            console.log(`🔌 Subscribed to quotes for ${data.symbol} in room ${data.room_id}`);
            this.connectedRooms.add(data.room_id);
            console.log(`🔌 Total connected rooms: ${this.connectedRooms.size}`);
            console.log(`🔌 Connected rooms:`, Array.from(this.connectedRooms));
            this.notifyRoomStateChange(); // Notify listeners
            console.log(`📢 Room state change notification sent after subscribing to ${data.symbol}`);
          }
          break;
          
        case 'bars_subscribed':
          if (data.room_id && data.symbol && data.interval) {
            console.log(`🔌 Subscribed to ${data.interval} bars for ${data.symbol} in room ${data.room_id}`);
            this.connectedRooms.add(data.room_id);
            console.log(`🔌 Total connected rooms: ${this.connectedRooms.size}`);
            console.log(`🔌 Connected rooms:`, Array.from(this.connectedRooms));
            this.notifyRoomStateChange(); // Notify listeners
          }
          break;
          
        case 'quote_update':
          // Handle real-time quote updates from room broadcasting
          if (data.data && this.isQuoteData(data.data)) {
            this.handleQuoteUpdate(data.data);
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
      volume: quoteData.volume || 0,
      timestamp: quoteData.timestamp || new Date().toISOString()
    };
    
    // Emit to specific symbol subscribers
    const symbol = quoteData.symbol.toUpperCase();
    if (this.subscriptions.has(symbol)) {
      this.subscriptions.get(symbol)!(formattedQuote);
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
    return typeof candidate.symbol === 'string' && typeof candidate.price === 'number';
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

  private handleClose(event: CloseEvent) {
    console.log('WebSocket disconnected:', event.code, event.reason);
    this.isConnecting = false;
    this.isDisconnecting = false;
    this.lastConnectionStatus = 'disconnected';
    this.notifyRoomStateChange(); // Notify status change
    
    // Clear local room tracking but keep subscriptions for reconnection
    this.connectedRooms.clear();
    
    // Schedule reconnection if enabled
    console.log(`🔍 Reconnection check: shouldReconnect=${this.shouldReconnect}, reconnectAttempts=${this.reconnectAttempts}, maxReconnectAttempts=${this.maxReconnectAttempts}`);
    if (this.shouldReconnect) {
      console.log(`🔄 Scheduling reconnection after disconnect...`);
      this.scheduleReconnect();
    } else {
      console.log(`⚠️ Reconnection disabled, not scheduling reconnect`);
    }
  }

  private handleError(error: Event) {
    console.error('WebSocket error:', error);
    if (!this.isDisconnecting) {
      this.lastConnectionStatus = 'disconnected';
      this.notifyRoomStateChange(); // Notify status change
      
      // Also try to reconnect on error if not already reconnecting
      if (this.shouldReconnect && !this.reconnectTimer) {
        console.log(`🔄 Scheduling reconnection after error...`);
        this.scheduleReconnect();
      }
    }
  }

  // Method to gracefully disconnect
  disconnect() {
    console.log('🔄 Manual disconnect initiated');
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
    console.log(`🔍 scheduleReconnect called: reconnectTimer=${!!this.reconnectTimer}, reconnectAttempts=${this.reconnectAttempts}, maxReconnectAttempts=${this.maxReconnectAttempts}, shouldReconnect=${this.shouldReconnect}`);
    
    if (this.reconnectTimer) {
      console.log(`⚠️ Reconnection timer already exists, skipping`);
      return;
    }
    
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log(`❌ Max reconnection attempts reached (${this.reconnectAttempts}/${this.maxReconnectAttempts}), stopping reconnection`);
      this.shouldReconnect = false;
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000); // Exponential backoff, max 30s
    
    console.log(`🔄 Scheduling reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`);
    
    this.reconnectTimer = setTimeout(() => {
      console.log(`⏰ Reconnection timer fired for attempt ${this.reconnectAttempts}`);
      this.reconnectTimer = null;
      if (this.shouldReconnect) {
        console.log(`🔄 Attempting reconnection ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
        this.connect();
      } else {
        console.log(`⚠️ Reconnection disabled, not attempting to connect`);
      }
    }, delay);
  }

  private resubscribeAll() {
    console.log('🔄 Re-subscribing to all active subscriptions after reconnection');
    console.log(`📊 Total subscriptions to restore: ${this.subscriptions.size + this.barsSubscriptions.size}`);
    
    let restoredCount = 0;
    
    // Re-subscribe to all active subscriptions
    this.subscriptions.forEach((_callback, symbol) => {
      console.log(`🔄 Re-subscribing to quotes for ${symbol}`);
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
        console.log(`🔄 Re-subscribing to bars for ${symbol}:${interval}`);
        try {
          this.subscribeToBars(symbol, interval);
          restoredCount++;
        } catch (error) {
          console.error(`❌ Failed to re-subscribe to bars for ${symbol}:${interval}:`, error);
        }
      }
    });
    
    console.log(`✅ Successfully restored ${restoredCount} subscriptions`);
    
    // Notify components that subscriptions have been restored
    setTimeout(() => {
      console.log(`📢 Notifying components of subscription restoration`);
      this.notifyRoomStateChange();
    }, 100); // Small delay to ensure backend has processed subscriptions
  }

  // Subscribe to quotes
  subscribe(symbol: string, callback: (data: QuotePayload) => void): () => void {
    const upperSymbol = symbol.toUpperCase();
    console.log(`🔌 wsClient.subscribe called for ${upperSymbol}`);
    
    // Store the subscription
    this.subscriptions.set(upperSymbol, callback);
    console.log(`💾 Stored subscription for ${upperSymbol}, total subscriptions: ${this.subscriptions.size}`);
    
    // Subscribe if connected
    if (this.isReady()) {
      console.log(`🌐 WebSocket ready, calling subscribeToQuotes for ${upperSymbol}`);
      this.subscribeToQuotes(upperSymbol);
    } else {
      console.log(`⚠️ WebSocket not ready, will subscribe later for ${upperSymbol}`);
    }
    
    // Return unsubscribe function
    const unsubscribeFn = () => {
      console.log(`🚪 Unsubscribe function called for ${upperSymbol}`);
      console.log(`🔍 Removing subscription for ${upperSymbol}...`);
      this.subscriptions.delete(upperSymbol);
      console.log(`🗑️ Subscription removed for ${upperSymbol}, remaining subscriptions: ${this.subscriptions.size}`);
      console.log(`🔌 Calling unsubscribeFromQuotes for ${upperSymbol}...`);
      this.unsubscribeFromQuotes(upperSymbol);
      console.log(`✅ Unsubscribe function completed for ${upperSymbol}`);
      
      // 🔥 Notify room state change after subscription removal
      this.notifyRoomStateChange();
    };
    
    console.log(`📤 Returning unsubscribe function for ${upperSymbol}`);
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
      console.log(`❌ WebSocket not ready, cannot subscribe to quotes for ${symbol}`);
      return;
    }
    
    const message = {
      type: 'subscribe',
      symbol: symbol
    };
    
    console.log(`📤 Sending subscribe message for ${symbol}:`, message);
    try {
      this.ws?.send(JSON.stringify(message));
      console.log(`✅ Subscribe message sent successfully for ${symbol}`);
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
    console.log(`🔌 unsubscribeFromQuotes called for ${symbol}`);
    // Find the room for this symbol and leave it
    const roomId = `quotes:${symbol}`;
    console.log(`🔍 Looking for room: ${roomId}`);
    console.log(`🔌 Current connected rooms:`, Array.from(this.connectedRooms));
    
    if (this.connectedRooms.has(roomId)) {
      console.log(`✅ Found room ${roomId}, leaving it...`);
      this.leaveRoom(roomId);
    } else {
      console.log(`⚠️ Room ${roomId} not found in connectedRooms`);
      console.log(`🔍 This might mean the room was never joined or already left`);
    }
  }

  private unsubscribeFromBars(symbol: string, interval: string) {
    console.log(`🔌 unsubscribeFromBars called for ${symbol}:${interval}`);
    // Find the room for this symbol/interval and leave it
    const roomId = `bars:${symbol}:${interval}`;
    console.log(`🔍 Looking for room: ${roomId}`);
    console.log(`🔌 Current connected rooms:`, Array.from(this.connectedRooms));
    
    if (this.connectedRooms.has(roomId)) {
      console.log(`✅ Found room ${roomId}, leaving it...`);
      this.leaveRoom(roomId);
    } else {
      console.log(`⚠️ Room ${roomId} not found in connectedRooms`);
      console.log(`🔍 This might mean the room was never joined or already left`);
    }
  }

  private leaveRoom(roomId: string) {
    console.log(`🚪 leaveRoom called for room: ${roomId}`);
    if (!this.isReady()) {
      console.log(`❌ WebSocket not ready, cannot leave room ${roomId}`);
      return;
    }
    
    const message = {
      type: 'leave_room',
      room_id: roomId
    };
    
    console.log(`📤 Sending leave_room message to backend:`, message);
    try {
      this.ws?.send(JSON.stringify(message));
      console.log(`✅ leave_room message sent successfully for ${roomId}`);
      
      // 🔥 Notify room state change after leaving room
      // Note: We don't remove from connectedRooms here because the backend will send a 'room_left' message
      // which will handle the removal and trigger another notification
    } catch (error) {
      console.error(`❌ Error sending leave_room message for ${roomId}:`, error);
    }
  }

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
    console.log(`🔔 Manual room state change trigger called`);
    this.notifyRoomStateChange();
  }

  // Manually trigger reconnection
  triggerReconnect() {
    console.log(`🔄 Manual reconnection triggered`);
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
    console.log(`🔍 Checking reconnection state: shouldReconnect=${this.shouldReconnect}, reconnectAttempts=${this.reconnectAttempts}, reconnectTimer=${!!this.reconnectTimer}, status=${this.getStatus()}`);
    
    if (this.getStatus() === 'disconnected' && this.shouldReconnect && !this.reconnectTimer) {
      console.log(`🔄 Force reconnection needed, calling scheduleReconnect`);
      this.scheduleReconnect();
    } else if (this.getStatus() === 'disconnected' && !this.shouldReconnect) {
      console.log(`⚠️ Reconnection disabled, enabling and scheduling reconnect`);
      this.shouldReconnect = true;
      this.reconnectAttempts = 0;
      this.scheduleReconnect();
    } else {
      console.log(`ℹ️ Reconnection state OK or already in progress`);
    }
  }

  // Reset reconnection settings
  resetReconnection() {
    console.log(`🔄 Resetting reconnection settings`);
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
    this.shouldReconnect = true;
  }

  // Manually sync all subscriptions
  syncSubscriptions() {
    console.log(`🔄 Manual subscription sync triggered`);
    if (this.isReady()) {
      console.log(`📊 Current subscriptions: ${this.subscriptions.size} quotes, ${this.barsSubscriptions.size} bars`);
      this.resubscribeAll();
    } else {
      console.log(`❌ WebSocket not ready, cannot sync subscriptions`);
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