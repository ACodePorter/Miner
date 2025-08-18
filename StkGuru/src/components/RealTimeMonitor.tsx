import React, { useState, useEffect, useCallback } from 'react';
import { wsClient } from '../utils/wsClient';

interface RealTimeMonitorProps {
  className?: string;
}

interface PerformanceMetrics {
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'disconnecting';
  connectedRooms: string[];
  roomCount: number;
  connectionUptime: number;
  lastUpdate: number;
  totalQuotes: number;
  totalBars: number;
  connectionStartTime: number;
}

const RealTimeMonitor: React.FC<RealTimeMonitorProps> = ({ className = '' }) => {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [forceUpdate, setForceUpdate] = useState(0);

  // Force update function to trigger re-renders when WebSocket state changes
  const triggerUpdate = useCallback(() => {
    setForceUpdate(prev => prev + 1);
  }, []);

  // Update metrics function
  const updateMetrics = useCallback(() => {
    const status = wsClient.getStatus();
    const connectedRooms = wsClient.getConnectedRooms();
    const roomCount = connectedRooms.length;
    
    // Calculate uptime (simplified - just track when we started monitoring)
    const now = Date.now();
    const connectionStartTime = metrics?.connectionStartTime || now;
    const connectionUptime = now - connectionStartTime;
    
    const newMetrics: PerformanceMetrics = {
      connectionStatus: status,
      connectedRooms,
      roomCount,
      connectionUptime,
      lastUpdate: now,
      totalQuotes: 0, // We'll track these separately if needed
      totalBars: 0,   // We'll track these separately if needed
      connectionStartTime
    };
    
    setMetrics(newMetrics);
  }, [metrics?.connectionStartTime]);

  useEffect(() => {
    // Update metrics every second
    const interval = setInterval(updateMetrics, 1000);
    updateMetrics(); // Initial update

    return () => clearInterval(interval);
  }, [updateMetrics, forceUpdate]); // Add forceUpdate dependency

  // Listen for WebSocket connection state changes and room events
  useEffect(() => {
    // Subscribe to room state change events from WebSocket client
    const unsubscribeRoomStateChange = wsClient.onRoomStateChange(() => {
      triggerUpdate();
    });

    // Poll for WebSocket state changes more frequently for better real-time updates
    const wsStateInterval = setInterval(() => {
      const currentStatus = wsClient.getStatus();
      const currentRooms = wsClient.getConnectedRooms();
      
      // Check if status or rooms have changed
      if (metrics) {
        if (currentStatus !== metrics.connectionStatus || 
            currentRooms.length !== metrics.roomCount ||
            JSON.stringify(currentRooms.sort()) !== JSON.stringify(metrics.connectedRooms.sort())) {
          triggerUpdate();
        }
      }
    }, 200); // Check every 200ms for more responsive updates

    // Periodic reconnection check for disconnected state
    const reconnectionCheckInterval = setInterval(() => {
      if (wsClient.getStatus() === 'disconnected') {
        wsClient.checkAndForceReconnect();
      }
    }, 5000); // Check every 5 seconds

    return () => {
      unsubscribeRoomStateChange();
      clearInterval(wsStateInterval);
      clearInterval(reconnectionCheckInterval);
    };
  }, [metrics, triggerUpdate]);

  if (!metrics) return null;

  const formatTime = (timestamp: number) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${Math.round(ms / 1000)}s`;
    return `${Math.round(ms / 60000)}m`;
  };

  // Add manual refresh button
  const handleManualRefresh = () => {
    triggerUpdate();
  };

  return (
    <div className={`fixed bottom-4 right-4 z-50 ${className}`}>
      {/* Toggle Button */}
      <button
        onClick={() => setIsVisible(!isVisible)}
        className="mb-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg shadow-lg transition-all duration-200"
      >
        {isVisible ? 'Hide' : 'Show'} Real-Time Monitor
      </button>

      {/* Monitor Panel */}
      {isVisible && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 shadow-2xl max-w-md">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full animate-pulse ${
                metrics.connectionStatus === 'connected' ? 'bg-green-400' : 'bg-red-400'
              }`}></div>
              Real-Time Performance
            </h3>
            <button
              onClick={handleManualRefresh}
              className="px-2 py-1 bg-slate-600 hover:bg-slate-500 text-white text-xs rounded transition-colors"
              title="Refresh metrics"
            >
              ↻
            </button>
          </div>

          {/* Connection Status */}
          <div className="mb-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-300">Status:</span>
              <span className={`px-2 py-1 rounded text-xs font-medium ${
                metrics.connectionStatus === 'connected' 
                  ? 'bg-green-900 text-green-300' 
                  : metrics.connectionStatus === 'connecting'
                  ? 'bg-yellow-900 text-yellow-300'
                  : metrics.connectionStatus === 'disconnecting'
                  ? 'bg-orange-900 text-orange-300'
                  : 'bg-red-900 text-red-300'
              }`}>
                {metrics.connectionStatus}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-300">Uptime:</span>
              <span className="text-slate-100 font-mono">
                {formatDuration(metrics.connectionUptime)}
              </span>
            </div>
            {/* Reconnection Controls */}
            {metrics.connectionStatus !== 'connected' && (
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => wsClient.triggerReconnect()}
                  className="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded transition-colors"
                  title="Reconnect WebSocket"
                >
                  🔄 Reconnect
                </button>
                <button
                  onClick={() => wsClient.checkAndForceReconnect()}
                  className="px-2 py-1 bg-yellow-600 hover:bg-yellow-700 text-white text-xs rounded transition-colors"
                  title="Check and force reconnection"
                >
                  🔍 Check
                </button>
                <button
                  onClick={() => wsClient.resetReconnection()}
                  className="px-2 py-1 bg-slate-600 hover:bg-slate-700 text-white text-xs rounded transition-colors"
                  title="Reset reconnection settings"
                >
                  🔧 Reset
                </button>
              </div>
            )}
            {/* Connection Controls */}
            {metrics.connectionStatus === 'connected' && (
              <div className="mt-2">
                <button
                  onClick={() => wsClient.disconnect()}
                  className="px-2 py-1 bg-red-600 hover:bg-red-700 text-white text-xs rounded transition-colors"
                  title="Disconnect WebSocket"
                >
                  ❌ Disconnect
                </button>
              </div>
            )}
          </div>

          {/* Update Counts */}
          <div className="mb-4">
            <h4 className="text-sm font-medium text-slate-200 mb-2">Update Counts</h4>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Quotes:</span>
                <span className="text-slate-100 font-mono">{metrics.totalQuotes}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Bars:</span>
                <span className="text-slate-100 font-mono">{metrics.totalBars}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Connected Rooms:</span>
                <span className="text-slate-100 font-mono">{metrics.roomCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Last Update:</span>
                <span className="text-slate-100 font-mono">{formatTime(metrics.lastUpdate)}</span>
              </div>
            </div>
          </div>

          {/* Last Update */}
          <div className="mb-4">
            <h4 className="text-sm font-medium text-slate-200 mb-2">Last Update</h4>
            <div className="text-xs text-slate-100 font-mono">
              {formatTime(metrics.lastUpdate)}
            </div>
          </div>

          {/* Connected Rooms */}
          {metrics.connectedRooms.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-medium text-slate-200 mb-2">
                Connected Rooms ({metrics.roomCount})
              </h4>
              <div className="max-h-32 overflow-y-auto">
                {metrics.connectedRooms.map((roomId) => (
                  <div key={roomId} className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400 truncate max-w-32">{roomId}</span>
                    <span className="text-slate-100 font-mono ml-2">✓</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Performance Tips */}
          <div className="text-xs text-slate-400 border-t border-slate-700 pt-3">
            <div className="font-medium mb-1">Room Management Tips:</div>
            <ul className="space-y-1">
              <li>• Each room represents a market data subscription</li>
              <li>• Monitor room count for active subscriptions</li>
              <li>• Check connection status for WebSocket health</li>
              <li>• Use refresh button (↻) to force update</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default RealTimeMonitor;
