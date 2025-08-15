import { apiConfig } from '../config/environment';

export type QuotePayload = {
  symbol: string;
  price: number;
  change?: number;
  changePercent?: number;
  volume?: number;
  marketCap?: number;
  timestamp?: string;
};

export type Bar = {
  timestamp: number; // ms UTC
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type BarsPayload = {
  symbol: string;
  interval: string;
  bars: Bar[];
  is_snapshot?: boolean;
};

type Message = {
  type: string;
  data?: any;
  symbol?: string;
  interval?: string;
  timestamp?: string;
  message?: string;
  client_id?: string;
};

type QuoteListener = (quote: QuotePayload) => void;

function makeWsUrl(): string {
  try {
    const base = new URL(apiConfig.baseUrl);
    const protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${base.host}/ws/${getClientId()}`;
  } catch {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/${getClientId()}`;
  }
}

function getClientId(): string {
  const key = 'stkguru_ws_client_id';
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}

class WSClient {
  private ws: WebSocket | null = null;
  private connected = false;
  private pending: string[] = [];
  private listeners: Map<string, Set<QuoteListener>> = new Map();
  private refCount: Map<string, number> = new Map();
  private barsListeners: Map<string, Set<(payload: BarsPayload) => void>> = new Map();
  private barsRefCount: Map<string, number> = new Map();
  private pingTimer: any = null;
  private reconnectTimer: any = null;
  
  // NEW: Subscription registry for better state management
  private subscriptionRegistry: Map<string, {
    listeners: Set<QuoteListener>;
    refCount: number;
    subscribed: boolean;
    lastAttempt: number;
  }> = new Map();
  
  // Performance monitoring
  private updateCounts: Map<string, number> = new Map();
  private lastUpdateTime: Map<string, number> = new Map();
  private performanceMetrics = {
    totalQuotes: 0,
    totalBars: 0,
    lastUpdate: Date.now(),
    connectionStartTime: Date.now()
  };

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return;
    const url = makeWsUrl();
    console.log('Connecting to WebSocket:', url);
    this.ws = new WebSocket(url);
    this.ws.onopen = () => {
      console.log('WebSocket connected successfully');
      this.connected = true;
      // Update connection start time when actually connected
      this.performanceMetrics.connectionStartTime = Date.now();
      
      // flush pending messages
      console.log(`Flushing ${this.pending.length} pending messages`);
      for (const msg of this.pending) {
        console.log('Sending pending message:', msg);
        this.ws?.send(msg);
      }
      this.pending = [];
      
      // NEW: Process all pending subscriptions from the registry
      console.log('Processing pending subscriptions from registry after connection');
      for (const [symbol, entry] of this.subscriptionRegistry.entries()) {
        if (!entry.subscribed) {
          console.log(`Processing pending subscription for ${symbol}`);
          this.attemptSubscription(symbol);
        }
      }
      
      // ping
      if (this.pingTimer) clearInterval(this.pingTimer);
      this.pingTimer = setInterval(() => {
        console.log('Sending ping message');
        this.send({ type: 'ping' });
      }, 30000);
    };
    this.ws.onclose = () => {
      this.connected = false;
      if (this.pingTimer) clearInterval(this.pingTimer);
      this.scheduleReconnect();
    };
    this.ws.onerror = () => {
      this.connected = false;
      this.ws?.close();
    };
    this.ws.onmessage = (ev) => {
      try {
        const raw = ev.data;
        console.log('Raw WebSocket data:', raw);
        console.log('Raw data type:', typeof raw);
        
        let msg: Message;
        try {
          msg = typeof raw === 'string' ? JSON.parse(raw) : raw;
        } catch (parseError) {
          console.error('Failed to parse WebSocket message:', parseError);
          console.error('Raw data was:', raw);
          return;
        }
        
        console.log('Parsed message:', msg);
        console.log('Message type:', msg?.type);
        console.log('Message type typeof:', typeof msg?.type);
        console.log('Message type length:', msg?.type?.length);
        console.log('Message type char codes:', msg?.type?.split('').map(c => c.charCodeAt(0)));
        console.log('Message structure:', JSON.stringify(msg, null, 2));
        
        if (msg?.type === 'quote' && msg.data && msg.data.symbol) {
          const sym = String(msg.data.symbol).toUpperCase();
          
          // NEW: Use subscription registry instead of legacy listeners map
          const entry = this.subscriptionRegistry.get(sym);
          
          // Debug: Show what listeners are registered and what we're looking for
          console.log(`WebSocket: Looking for listeners for symbol: ${sym}`);
          console.log(`WebSocket: Registry entry exists: ${!!entry}`);
          console.log(`WebSocket: Total registry entries: ${this.subscriptionRegistry.size}`);
          console.log(`WebSocket: Registry keys:`, Array.from(this.subscriptionRegistry.keys()));
          if (entry) {
            console.log(`WebSocket: Registry entry - subscribed: ${entry.subscribed}, refs: ${entry.refCount}, listeners: ${entry.listeners.size}`);
          }
          
          if (entry && entry.listeners.size > 0) {
            console.log(`Dispatching quote to ${entry.listeners.size} listeners for ${sym}`);
            
            // Update performance metrics
            this.performanceMetrics.totalQuotes++;
            this.performanceMetrics.lastUpdate = Date.now();
            this.updateCounts.set(sym, (this.updateCounts.get(sym) || 0) + 1);
            this.lastUpdateTime.set(sym, Date.now());
            
            entry.listeners.forEach((fn) => fn(msg.data as QuotePayload));
          } else {
            console.log(`WebSocket: No listeners found for ${sym}`);
            console.log(`WebSocket: This might mean the subscription hasn't been confirmed yet, or there's a timing issue`);
          }
        } else if (msg?.type === 'bars' && msg.data && msg.data.symbol && msg.data.interval) {
          const sym = String(msg.data.symbol).toUpperCase();
          const interval = String(msg.data.interval);
          const key = `${sym}|${interval}`;
          const ls = this.barsListeners.get(key);
          if (ls && ls.size) {
            console.log(`Dispatching bars to ${ls.size} listeners for ${key}:`, msg.data);
            
            // Update performance metrics
            this.performanceMetrics.totalBars++;
            this.performanceMetrics.lastUpdate = Date.now();
            this.updateCounts.set(key, (this.updateCounts.get(key) || 0) + 1);
            this.lastUpdateTime.set(key, Date.now());
            
            ls.forEach((fn) => fn(msg.data as BarsPayload));
          } else {
            console.log(`No bars listeners found for ${key}`);
          }
        } else if (msg?.type === 'unsubscribed' && msg.symbol) {
          // Handle server confirmation of unsubscription
          const sym = String(msg.symbol).toUpperCase();
          console.log(`Server confirmed unsubscription for ${sym}`);
          
          // Clean up internal state for quotes
          if (this.listeners.has(sym)) {
            this.listeners.delete(sym);
            this.refCount.delete(sym);
            this.updateCounts.delete(sym);
            this.lastUpdateTime.delete(sym);
            console.log(`Cleaned up quote subscription state for ${sym}`);
          }
          
          // Clean up internal state for bars (check all intervals)
          for (const [key, _] of this.barsListeners.entries()) {
            if (key.startsWith(`${sym}|`)) {
              this.barsListeners.delete(key);
              this.barsRefCount.delete(key);
              this.updateCounts.delete(key);
              this.lastUpdateTime.delete(key);
              console.log(`Cleaned up bars subscription state for ${key}`);
            }
          }
        } else if (msg?.type === 'bars_unsubscribed' && msg.symbol && msg.interval) {
          // Handle server confirmation of bars unsubscription
          const sym = String(msg.symbol).toUpperCase();
          const interval = String(msg.interval);
          const key = `${sym}|${interval}`;
          console.log(`Server confirmed bars unsubscription for ${key}`);
          
          // Clean up internal state for bars
          if (this.barsListeners.has(key)) {
            this.barsListeners.delete(key);
            this.barsRefCount.delete(key);
            this.updateCounts.delete(key);
            this.lastUpdateTime.delete(key);
            console.log(`Cleaned up bars subscription state for ${key}`);
          }
        } else if (msg?.type === 'pong') {
          // Handle pong response to ping
          console.log('Received pong from server');
        } else if (msg?.type === 'connected') {
          // Handle connection confirmation
          console.log('Connected to WebSocket server:', msg.message);
        } else if (msg?.type === 'subscribed') {
          // Handle subscription confirmation
          const sym = String(msg.symbol).toUpperCase();
          console.log(`Subscription confirmed for ${sym}`);
          
          // NEW: Mark subscription as confirmed in registry
          const entry = this.subscriptionRegistry.get(sym);
          if (entry) {
            entry.subscribed = true;
            console.log(`Marked ${sym} as subscribed in registry`);
          }
        } else if (msg?.type === 'bars_subscribed') {
          // Handle bars subscription confirmation
          console.log(`Bars subscription confirmed for ${msg.symbol} ${msg.interval}`);
        } else if (msg?.type === 'error') {
          // Handle error messages
          console.error('WebSocket error from server:', msg.message);
        } else if (msg?.type === 'broadcast_sent') {
          // Handle broadcast confirmation
          console.log('Broadcast message sent:', msg.message);
        } else {
          console.log('Unknown or malformed message type:', msg?.type);
        }
      } catch (error) {
        console.error('Error processing WebSocket message:', error);
      }
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 2000);
  }

  private send(obj: any) {
    const text = JSON.stringify(obj);
    console.log('Sending WebSocket message:', obj);
    if (this.connected && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(text);
    } else {
      this.pending.push(text);
      this.connect();
    }
  }

  subscribe(symbol: string, listener: QuoteListener): () => void {
    const sym = symbol.toUpperCase();
    
    // Get or create subscription entry
    let entry = this.subscriptionRegistry.get(sym);
    if (!entry) {
      entry = {
        listeners: new Set(),
        refCount: 0,
        subscribed: false,
        lastAttempt: 0
      };
      this.subscriptionRegistry.set(sym, entry);
    }
    
    // Add listener and increment ref count
    entry.listeners.add(listener);
    entry.refCount++;
    
    console.log(`WebSocket: Subscribing to ${sym}, refs: ${entry.refCount}, listeners: ${entry.listeners.size}`);
    console.log(`WebSocket: Connection ready: ${this.isReady()}, already subscribed: ${entry.subscribed}`);
    console.log(`WebSocket: Registry now has ${this.subscriptionRegistry.size} entries:`, Array.from(this.subscriptionRegistry.keys()));
    
    // Try to subscribe if not already subscribed and connection is ready
    if (!entry.subscribed && this.isReady()) {
      console.log(`WebSocket: Attempting subscription for ${sym}`);
      this.attemptSubscription(sym);
    } else if (!entry.subscribed) {
      console.log(`WebSocket: Connection not ready, will subscribe to ${sym} when connected`);
    }
    
    // Return unsubscribe function
    return () => {
      if (!entry) return;
      
      entry.listeners.delete(listener);
      entry.refCount--;
      
      console.log(`WebSocket: Unsubscribing from ${sym}, remaining refs: ${entry.refCount}`);
      
      // If no more listeners, unsubscribe from server
      if (entry.refCount <= 0) {
        if (entry.subscribed && this.isReady()) {
          console.log(`WebSocket: Sending unsubscribe for ${sym}`);
          this.send({ type: 'unsubscribe', symbol: sym });
        }
        this.subscriptionRegistry.delete(sym);
        this.listeners.delete(sym);
        this.refCount.delete(sym);
        console.log(`WebSocket: Removed ${sym} from registry, remaining:`, Array.from(this.subscriptionRegistry.keys()));
      }
    };
  }
  
  // NEW: Attempt subscription with retry logic
  private attemptSubscription(symbol: string): void {
    const entry = this.subscriptionRegistry.get(symbol);
    if (!entry || entry.subscribed) return;
    
    const now = Date.now();
    const retryDelay = 1000; // 1 second
    
    // Check if we should retry
    if (now - entry.lastAttempt < retryDelay) {
      console.log(`WebSocket: Skipping subscription attempt for ${symbol}, too soon since last attempt`);
      return;
    }
    
    entry.lastAttempt = now;
    
    if (this.isReady()) {
      console.log(`WebSocket: Attempting subscription for ${symbol}`);
      this.send({ type: 'subscribe', symbol });
      
      // NEW: Set a timeout to auto-confirm subscription if server doesn't respond
      setTimeout(() => {
        const currentEntry = this.subscriptionRegistry.get(symbol);
        if (currentEntry && !currentEntry.subscribed) {
          console.log(`WebSocket: Auto-confirming subscription for ${symbol} after timeout (server may not send confirmation)`);
          currentEntry.subscribed = true;
          
          // Update the legacy listeners map for backward compatibility
          this.listeners.set(symbol, currentEntry.listeners);
          this.refCount.set(symbol, currentEntry.refCount);
          
          console.log(`WebSocket: ${symbol} is now marked as subscribed and ready to receive quotes`);
        }
      }, 2000); // Wait 2 seconds for server confirmation, then auto-confirm
      
      // Don't mark as subscribed immediately - wait for confirmation or timeout
      console.log(`WebSocket: Subscription request sent for ${symbol}, waiting for confirmation or timeout`);
    } else {
      console.log(`WebSocket: Cannot subscribe to ${symbol}, connection not ready`);
      entry.subscribed = false;
    }
  }

  subscribeBars(symbol: string, interval: string, listener: (payload: BarsPayload) => void): () => void {
    const sym = symbol.toUpperCase();
    const key = `${sym}|${interval}`;
    const current = this.barsRefCount.get(key) || 0;
    this.barsRefCount.set(key, current + 1);
    if (!this.barsListeners.has(key)) this.barsListeners.set(key, new Set());
    this.barsListeners.get(key)!.add(listener);
    console.log(`Subscribing to bars: ${key}, current refs: ${current + 1}`);
    if (current === 0) {
      console.log(`Sending subscribe_bars message for ${key}`);
      this.send({ type: 'subscribe_bars', symbol: sym, interval });
    }
    // return unsubscribe
    return () => {
      const set = this.barsListeners.get(key);
      if (set) set.delete(listener);
      const cnt = (this.barsRefCount.get(key) || 1) - 1;
      this.barsRefCount.set(key, Math.max(0, cnt));
      console.log(`Unsubscribing from bars: ${key}, remaining refs: ${cnt}`);
      if (cnt <= 0) {
        console.log(`Sending unsubscribe_bars message for ${key}`);
        this.send({ type: 'unsubscribe_bars', symbol: sym, interval });
      }
    };
  }
  
  // Get performance metrics for monitoring
  getPerformanceMetrics() {
    const now = Date.now();
    return {
      ...this.performanceMetrics,
      connectionUptime: this.connected ? now - this.performanceMetrics.connectionStartTime : 0,
      updateCounts: Object.fromEntries(this.updateCounts),
      lastUpdateTimes: Object.fromEntries(this.lastUpdateTime),
      activeQuoteListeners: this.listeners.size,
      activeBarsListeners: this.barsListeners.size,
      connectionStatus: this.connected ? 'connected' : 'disconnected'
    };
  }
  
  // Get real-time update status for specific symbols
  getUpdateStatus(symbol: string, interval?: string) {
    const sym = symbol.toUpperCase();
    const key = interval ? `${sym}|${interval}` : sym;
    
    if (!interval) {
      // For quotes, use the new subscription registry
      const entry = this.subscriptionRegistry.get(sym);
      return {
        symbol: sym,
        interval,
        updateCount: this.updateCounts.get(key) || 0,
        lastUpdate: this.lastUpdateTime.get(key) || 0,
        hasListeners: entry ? entry.listeners.size > 0 : false,
        listenerCount: entry ? entry.listeners.size : 0,
        refCount: entry ? entry.refCount : 0,
        subscribed: entry ? entry.subscribed : false,
        lastAttempt: entry ? entry.lastAttempt : 0
      };
    } else {
      // For bars, use the existing bars listeners
      return {
        symbol: sym,
        interval,
        updateCount: this.updateCounts.get(key) || 0,
        lastUpdate: this.lastUpdateTime.get(key) || 0,
        hasListeners: this.barsListeners.has(key),
        listenerCount: this.barsListeners.get(key)?.size || 0,
        refCount: this.barsRefCount.get(key) || 0
      };
    }
  }
  
  // NEW: Get detailed subscription registry status for debugging
  getSubscriptionRegistryStatus() {
    const status: Record<string, any> = {};
    for (const [symbol, entry] of this.subscriptionRegistry.entries()) {
      status[symbol] = {
        subscribed: entry.subscribed,
        refCount: entry.refCount,
        listenerCount: entry.listeners.size,
        lastAttempt: entry.lastAttempt
      };
    }
    return status;
  }
  
  // NEW: Force confirm subscription for testing (when server doesn't send confirmation)
  forceConfirmSubscription(symbol: string): void {
    const sym = symbol.toUpperCase();
    const entry = this.subscriptionRegistry.get(sym);
    if (entry && !entry.subscribed) {
      console.log(`WebSocket: Force confirming subscription for ${sym}`);
      entry.subscribed = true;
      
      // Update the legacy listeners map for backward compatibility
      this.listeners.set(sym, entry.listeners);
      this.refCount.set(sym, entry.refCount);
      
      console.log(`WebSocket: ${sym} is now force-confirmed as subscribed`);
    } else if (entry) {
      console.log(`WebSocket: ${sym} is already subscribed`);
    } else {
      console.log(`WebSocket: No subscription entry found for ${sym}`);
    }
  }
  
  // Check if WebSocket is ready for subscriptions
  isReady(): boolean {
    return !!(this.connected && this.ws && this.ws.readyState === WebSocket.OPEN);
  }
  
  // Get connection status
  getConnectionStatus() {
    const activeSubscriptions = Array.from(this.subscriptionRegistry.values()).filter(entry => entry.subscribed).length;
    const pendingSubscriptions = Array.from(this.subscriptionRegistry.values()).filter(entry => !entry.subscribed).length;
    
    return {
      connected: this.connected,
      readyState: this.ws ? this.ws.readyState : undefined,
      isReady: this.isReady(),
      pendingMessages: this.pending.length,
      activeQuoteSubscriptions: activeSubscriptions,
      pendingQuoteSubscriptions: pendingSubscriptions,
      totalRegistryEntries: this.subscriptionRegistry.size,
      registryKeys: Array.from(this.subscriptionRegistry.keys())
    };
  }
}

export const wsClient = new WSClient();
wsClient.connect();


