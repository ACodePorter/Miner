import React, { useState } from 'react';
import { shouldShowExtensionWarning } from '../utils/browserUtils';

interface ExtensionWarningProps {
  onDismiss?: () => void;
}

const ExtensionWarning: React.FC<ExtensionWarningProps> = React.memo(({ onDismiss }) => {
  const [isVisible, setIsVisible] = useState(shouldShowExtensionWarning());

  if (!isVisible) {
    return null;
  }

  const handleDismiss = () => {
    setIsVisible(false);
    onDismiss?.();
  };

  const handleClearCache = () => {
    window.location.href = '/clear-cache.html';
  };

  return (
    <div className="fixed top-4 right-4 z-50 max-w-sm bg-yellow-900/90 backdrop-blur-sm border border-yellow-600/50 rounded-lg p-4 shadow-lg">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <svg className="w-5 h-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-medium text-yellow-200">
            Browser Extension Issue Detected
          </h3>
          <p className="mt-1 text-xs text-yellow-300">
            Chrome extensions may be interfering with the app. Try:
          </p>
          <ul className="mt-2 text-xs text-yellow-300 space-y-1">
            <li>• Opening in incognito mode</li>
            <li>• Disabling ad blockers</li>
            <li>• Clearing browser cache</li>
          </ul>
          <div className="mt-3 flex gap-2">
            <button
              onClick={handleClearCache}
              className="text-xs bg-yellow-600 hover:bg-yellow-700 text-white px-3 py-1 rounded transition-colors"
            >
              Clear Cache
            </button>
            <button
              onClick={handleDismiss}
              className="text-xs bg-gray-600 hover:bg-gray-700 text-white px-3 py-1 rounded transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
        <button
          onClick={handleDismiss}
          className="flex-shrink-0 text-yellow-400 hover:text-yellow-300"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>
      </div>
    </div>
  );
});

ExtensionWarning.displayName = 'ExtensionWarning';

export default ExtensionWarning; 