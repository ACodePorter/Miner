import { wsClient, type QuotePayload } from './wsClient';

interface SubscriptionInfo {
  ticker: string;
  subscribers: Map<string, (data: QuotePayload) => void>; // componentId -> callback function
  unsubscribe: () => void;
}

class SubscriptionManager {
  private subscriptions = new Map<string, SubscriptionInfo>();
  private componentSubscriptions = new Map<string, Set<string>>(); // componentId -> Set<ticker>

  // Subscribe to quotes for a specific ticker from a component
  subscribe(ticker: string, componentId: string, callback: (data: QuotePayload) => void): () => void {
    const upperTicker = ticker.toUpperCase();
    
    console.log(`🔔 SubscriptionManager: ${componentId} subscribing to ${upperTicker}`);
    
    // Initialize component's ticker set if it doesn't exist
    if (!this.componentSubscriptions.has(componentId)) {
      this.componentSubscriptions.set(componentId, new Set());
    }
    
    // Add ticker to component's subscriptions
    this.componentSubscriptions.get(componentId)!.add(upperTicker);
    
    // If ticker is already subscribed, just add the component to subscribers
    if (this.subscriptions.has(upperTicker)) {
      const subscription = this.subscriptions.get(upperTicker)!;
      subscription.subscribers.set(componentId, callback);
      
      console.log(`🔔 SubscriptionManager: ${componentId} added to existing ${upperTicker} subscription (total: ${subscription.subscribers.size})`);
      
      // Return unsubscribe function for this component
      return () => this.unsubscribeComponent(upperTicker, componentId);
    }
    
    // Create new subscription
    const unsubscribe = wsClient.subscribe(upperTicker, (data: QuotePayload) => {
      console.log(`📡 SubscriptionManager: Received quote for ${upperTicker}, broadcasting to ${this.subscriptions.get(upperTicker)?.subscribers.size || 0} subscribers`);
      
      // Broadcast to all subscribers
      const subscription = this.subscriptions.get(upperTicker);
      if (subscription) {
        subscription.subscribers.forEach((callback, subId) => {
          try {
            console.log(`📡 SubscriptionManager: Calling callback for ${subId} with ${upperTicker} quote`);
            callback(data);
          } catch (error) {
            console.error(`Error calling callback for component ${subId}:`, error);
          }
        });
      }
    });
    
    // Store subscription info with callback
    this.subscriptions.set(upperTicker, {
      ticker: upperTicker,
      subscribers: new Map([[componentId, callback]]),
      unsubscribe
    });
    
    console.log(`🔔 SubscriptionManager: Created new subscription for ${upperTicker} with ${componentId} (total: 1)`);
    
    // Return unsubscribe function for this component
    return () => this.unsubscribeComponent(upperTicker, componentId);
  }

  // Unsubscribe a component from a specific ticker
  unsubscribeComponent(ticker: string, componentId: string): void {
    const upperTicker = ticker.toUpperCase();
    
    console.log(`🔔 SubscriptionManager: ${componentId} unsubscribing from ${upperTicker}`);
    
    // Remove ticker from component's subscriptions
    const componentTickers = this.componentSubscriptions.get(componentId);
    if (componentTickers) {
      componentTickers.delete(upperTicker);
      
      // If component has no more tickers, remove it entirely
      if (componentTickers.size === 0) {
        this.componentSubscriptions.delete(componentId);
        console.log(`🔔 SubscriptionManager: Removed component ${componentId} (no more tickers)`);
      }
    }
    
    // Remove component from ticker's subscribers
    const subscription = this.subscriptions.get(upperTicker);
    if (subscription) {
      subscription.subscribers.delete(componentId);
      
      console.log(`🔔 SubscriptionManager: ${componentId} removed from ${upperTicker} subscribers (remaining: ${subscription.subscribers.size})`);
      
      // If no more subscribers, unsubscribe from WebSocket and remove subscription
      if (subscription.subscribers.size === 0) {
        console.log(`🔔 SubscriptionManager: No more subscribers for ${upperTicker}, unsubscribing from WebSocket`);
        subscription.unsubscribe();
        this.subscriptions.delete(upperTicker);
      }
    }
  }

  // Unsubscribe a component from all tickers (when component unmounts)
  unsubscribeComponentAll(componentId: string): void {
    const componentTickers = this.componentSubscriptions.get(componentId);
    if (componentTickers) {
      // Create a copy of the set to avoid modification during iteration
      const tickers = Array.from(componentTickers);
      tickers.forEach(ticker => {
        this.unsubscribeComponent(ticker, componentId);
      });
    }
  }

  // Get subscription count for a ticker
  getSubscriptionCount(ticker: string): number {
    const upperTicker = ticker.toUpperCase();
    const subscription = this.subscriptions.get(upperTicker);
    return subscription ? subscription.subscribers.size : 0;
  }

  // Get all active tickers
  getActiveTickers(): string[] {
    return Array.from(this.subscriptions.keys());
  }

  // Check if a ticker is subscribed
  isSubscribed(ticker: string): boolean {
    const upperTicker = ticker.toUpperCase();
    return this.subscriptions.has(upperTicker);
  }

  // Get debug information
  getDebugInfo() {
    return {
      totalSubscriptions: this.subscriptions.size,
      totalComponents: this.componentSubscriptions.size,
      subscriptions: Array.from(this.subscriptions.entries()).map(([ticker, info]) => ({
        ticker,
        subscriberCount: info.subscribers.size,
        subscribers: Array.from(info.subscribers.keys())
      })),
      components: Array.from(this.componentSubscriptions.entries()).map(([componentId, tickers]) => ({
        componentId,
        tickerCount: tickers.size,
        tickers: Array.from(tickers)
      }))
    };
  }
}

// Export singleton instance
export const subscriptionManager = new SubscriptionManager();
export default subscriptionManager;
