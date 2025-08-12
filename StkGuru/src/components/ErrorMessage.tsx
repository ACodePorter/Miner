import React from 'react';

interface ErrorMessageProps {
  message: string;
  className?: string;
}

const ErrorMessage: React.FC<ErrorMessageProps> = React.memo(({ message }) => {
  return (
    <div className="flex items-center space-x-2 p-2 text-red-400 bg-red-950/20 border border-red-800/30 rounded-lg">
      <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span className="text-xs">{message}</span>
    </div>
  );
});

ErrorMessage.displayName = 'ErrorMessage';

export default ErrorMessage; 