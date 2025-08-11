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
        if (msg?.type === 'quote' && msg.data && msg.data.symbol) {
          const sym = String(msg.data.symbol).toUpperCase();
          const ls = this.listeners.get(sym);
          if (ls && ls.size) {
            ls.forEach((fn) => fn(msg.data as QuotePayload));
          }
        }
      } catch {
        // ignore
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
}

export const wsClient = new WSClient();
wsClient.connect();


