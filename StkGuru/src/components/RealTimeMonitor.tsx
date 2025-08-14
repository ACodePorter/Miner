import React, { useState, useEffect } from 'react';
import { wsClient } from '../utils/wsClient';

interface RealTimeMonitorProps {
  className?: string;
}

interface PerformanceMetrics {
  totalQuotes: number;
  totalBars: number;
  lastUpdate: number;
  connectionStartTime: number;
  connectionUptime: number;
  updateCounts: Record<string, number>;
  lastUpdateTimes: Record<string, number>;
  activeQuoteListeners: number;
  activeBarsListeners: number;
  connectionStatus: string;
}

const RealTimeMonitor: React.FC<RealTimeMonitorProps> = ({ className = '' }) => {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const updateMetrics = () => {
      const newMetrics = wsClient.getPerformanceMetrics();
      setMetrics(newMetrics);
    };

    // Update metrics every second
    const interval = setInterval(updateMetrics, 1000);
    updateMetrics(); // Initial update

    return () => clearInterval(interval);
  }, []);

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
          <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            Real-Time Performance
          </h3>

          {/* Connection Status */}
          <div className="mb-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-300">Status:</span>
              <span className={`px-2 py-1 rounded text-xs font-medium ${
                metrics.connectionStatus === 'connected' 
                  ? 'bg-green-900 text-green-300' 
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
                <span className="text-slate-400">Quote Listeners:</span>
                <span className="text-slate-100 font-mono">{metrics.activeQuoteListeners}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Bar Listeners:</span>
                <span className="text-slate-100 font-mono">{metrics.activeBarsListeners}</span>
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

          {/* Active Subscriptions */}
          {Object.keys(metrics.updateCounts).length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-medium text-slate-200 mb-2">Active Subscriptions</h4>
              <div className="max-h-32 overflow-y-auto">
                {Object.entries(metrics.updateCounts).map(([key, count]) => (
                  <div key={key} className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400 truncate max-w-32">{key}:</span>
                    <span className="text-slate-100 font-mono ml-2">{count as number}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Performance Tips */}
          <div className="text-xs text-slate-400 border-t border-slate-700 pt-3">
            <div className="font-medium mb-1">Performance Tips:</div>
            <ul className="space-y-1">
              <li>• High update counts indicate active real-time data</li>
              <li>• Monitor connection uptime for stability</li>
              <li>• Check listener counts for subscription health</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default RealTimeMonitor;
