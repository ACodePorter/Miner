// Simple test script to verify WebSocket client performance metrics
// Run this in the browser console to test the client

console.log('🧪 Testing WebSocket Client Performance Metrics...');

// Test 1: Check if wsClient exists
if (typeof wsClient !== 'undefined') {
  console.log('✅ wsClient found');
  
  // Test 2: Check if performance metrics method exists
  if (typeof wsClient.getPerformanceMetrics === 'function') {
    console.log('✅ getPerformanceMetrics method found');
    
    // Test 3: Get initial metrics
    try {
      const metrics = wsClient.getPerformanceMetrics();
      console.log('✅ Initial metrics retrieved:', metrics);
      
      // Test 4: Check metrics structure
      const requiredFields = [
        'totalQuotes', 'totalBars', 'lastUpdate', 
        'connectionStartTime', 'connectionUptime',
        'updateCounts', 'lastUpdateTimes',
        'activeQuoteListeners', 'activeBarsListeners',
        'connectionStatus'
      ];
      
      const missingFields = requiredFields.filter(field => !(field in metrics));
      if (missingFields.length === 0) {
        console.log('✅ All required metrics fields present');
      } else {
        console.log('❌ Missing fields:', missingFields);
      }
      
      // Test 5: Check if getUpdateStatus method exists
      if (typeof wsClient.getUpdateStatus === 'function') {
        console.log('✅ getUpdateStatus method found');
        
        // Test 6: Test getUpdateStatus for a sample symbol
        try {
          const status = wsClient.getUpdateStatus('AAPL', '5m');
          console.log('✅ Update status for AAPL 5m:', status);
          
          const requiredStatusFields = [
            'symbol', 'interval', 'updateCount', 'lastUpdate',
            'hasListeners', 'listenerCount'
          ];
          
          const missingStatusFields = requiredStatusFields.filter(field => !(field in status));
          if (missingStatusFields.length === 0) {
            console.log('✅ All required status fields present');
          } else {
            console.log('❌ Missing status fields:', missingStatusFields);
          }
          
        } catch (error) {
          console.log('❌ Error testing getUpdateStatus:', error);
        }
        
      } else {
        console.log('❌ getUpdateStatus method not found');
      }
      
    } catch (error) {
      console.log('❌ Error getting performance metrics:', error);
    }
    
  } else {
    console.log('❌ getPerformanceMetrics method not found');
  }
  
  // Test 7: Check connection status
  console.log('📊 Current connection status:', {
    connected: wsClient.connected,
    wsState: wsClient.ws?.readyState
  });
  
} else {
  console.log('❌ wsClient not found - make sure you\'re on the Screener page');
}

console.log('🏁 WebSocket Client Test Complete!');
console.log('');
console.log('💡 To monitor real-time performance:');
console.log('1. Go to the Screener page');
console.log('2. Click "Show Real-Time Monitor"');
console.log('3. Watch the performance metrics update in real-time');
console.log('');
console.log('🔧 Debug commands:');
console.log('- wsClient.getPerformanceMetrics()');
console.log('- wsClient.getUpdateStatus("AAPL", "5m")');
