import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import ErrorBoundary from './components/ErrorBoundary.tsx'
import { clearExtensionInterference, shouldShowExtensionWarning } from './utils/browserUtils.ts'

// Prevent service worker errors from affecting the app
const preventServiceWorkerErrors = () => {
  // Override console.error to filter out service worker errors
  const originalError = console.error;
  console.error = (...args) => {
    const message = args.join(' ');
    if (message.includes('chrome-extension') || message.includes('sw.js')) {
      // Silently ignore service worker errors
      return;
    }
    originalError.apply(console, args);
  };

  // Clean up any existing service workers that might be causing issues
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then((registrations) => {
      for (const registration of registrations) {
        // Only unregister if it's not our own service worker
        if (!registration.scope.includes(window.location.origin)) {
          registration.unregister().catch(() => {
            // Ignore unregister errors
          });
        }
      }
    }).catch(() => {
      // Ignore service worker errors
    });
  }
};

// Initialize error prevention and extension cleanup
preventServiceWorkerErrors();

// Clear extension interference if needed
if (shouldShowExtensionWarning()) {
  clearExtensionInterference().catch(() => {
    // Ignore extension clearing errors
  });
}

// Error boundary for React hook errors
const root = createRoot(document.getElementById('root')!);

// Wrap the render in a try-catch to handle any initialization errors
try {
  root.render(
    <ErrorBoundary>
      <StrictMode>
        <App />
      </StrictMode>
    </ErrorBoundary>
  );
} catch (error) {
  console.error('Failed to render app:', error);
  // Fallback render without StrictMode
  try {
    root.render(
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    );
  } catch (fallbackError) {
    console.error('Fallback render also failed:', fallbackError);
    // Last resort: render a simple error message
    root.render(
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        backgroundColor: '#1f2937',
        color: 'white',
        fontFamily: 'system-ui, sans-serif'
      }}>
        <div style={{ textAlign: 'center' }}>
          <h1>StkGuru</h1>
          <p>Failed to load the application. Please refresh the page.</p>
          <button 
            onClick={() => window.location.reload()}
            style={{
              background: '#3b82f6',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '16px'
            }}
          >
            Refresh Page
          </button>
        </div>
      </div>
    );
  }
}
