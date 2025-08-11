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

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return;
    const url = makeWsUrl();
    this.ws = new WebSocket(url);
    this.ws.onopen = () => {
      this.connected = true;
      // flush
      for (const msg of this.pending) this.ws?.send(msg);
      this.pending = [];
      // resubscribe
      for (const [symbol, count] of this.refCount.entries()) {
        if (count > 0) this.send({ type: 'subscribe', symbol });
      }
      for (const [key, count] of this.barsRefCount.entries()) {
        if (count > 0) {
          const [symbol, interval] = key.split('|');
          this.send({ type: 'subscribe_bars', symbol, interval });
        }
      }
      // ping
      if (this.pingTimer) clearInterval(this.pingTimer);
      this.pingTimer = setInterval(() => this.send({ type: 'ping' }), 30000);
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
        const msg: Message = typeof raw === 'string' ? JSON.parse(raw) : raw;
        console.log('WebSocket received message:', msg);
        
        if (msg?.type === 'quote' && msg.data && msg.data.symbol) {
          const sym = String(msg.data.symbol).toUpperCase();
          const ls = this.listeners.get(sym);
          if (ls && ls.size) {
            console.log(`Dispatching quote to ${ls.size} listeners for ${sym}`);
            ls.forEach((fn) => fn(msg.data as QuotePayload));
          }
        } else if (msg?.type === 'bars' && msg.data && msg.data.symbol && msg.data.interval) {
          const sym = String(msg.data.symbol).toUpperCase();
          const interval = String(msg.data.interval);
          const key = `${sym}|${interval}`;
          const ls = this.barsListeners.get(key);
          if (ls && ls.size) {
            console.log(`Dispatching bars to ${ls.size} listeners for ${key}:`, msg.data);
            ls.forEach((fn) => fn(msg.data as BarsPayload));
          } else {
            console.log(`No bars listeners found for ${key}`);
          }
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
    if (this.connected && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(text);
    } else {
      this.pending.push(text);
      this.connect();
    }
  }

  subscribe(symbol: string, listener: QuoteListener): () => void {
    const sym = symbol.toUpperCase();
    const current = this.refCount.get(sym) || 0;
    this.refCount.set(sym, current + 1);
    if (!this.listeners.has(sym)) this.listeners.set(sym, new Set());
    this.listeners.get(sym)!.add(listener);
    if (current === 0) this.send({ type: 'subscribe', symbol: sym });
    // return unsubscribe
    return () => {
      const set = this.listeners.get(sym);
      if (set) set.delete(listener);
      const cnt = (this.refCount.get(sym) || 1) - 1;
      this.refCount.set(sym, Math.max(0, cnt));
      if (cnt <= 0) this.send({ type: 'unsubscribe', symbol: sym });
    };
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
}

export const wsClient = new WSClient();
wsClient.connect();


