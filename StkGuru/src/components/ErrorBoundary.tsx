import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      
      return (
        <div className="flex items-center justify-center min-h-screen bg-gradient-primary text-text-primary p-8">
          <div className="text-center max-w-md">
            <div className="w-20 h-20 mx-auto mb-6 bg-danger-950/20 rounded-full flex items-center justify-center">
              <svg className="w-10 h-10 text-danger-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-danger-400 mb-4">Something went wrong</h2>
            <p className="text-text-secondary mb-6">
              The application encountered an error. Please try refreshing the page.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="btn-primary px-6 py-3 rounded-lg font-medium"
            >
              Refresh Page
            </button>
            {import.meta.env.DEV && this.state.error && (
              <details className="mt-4 text-left">
                <summary className="cursor-pointer text-text-tertiary hover:text-text-secondary">
                  Error Details (Development)
                </summary>
                <pre className="mt-2 text-xs text-danger-300 bg-bg-tertiary p-3 rounded overflow-auto border border-border-primary">
                  {this.state.error.stack}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary; 