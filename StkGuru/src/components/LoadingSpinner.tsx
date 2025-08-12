import React from 'react';

interface LoadingSpinnerProps {
  text?: string;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ text }) => {
  return (
    <div className="flex flex-col items-center justify-center py-4">
      <div className="w-8 h-8 border-2 border-slate-600 border-t-blue-400 rounded-full animate-spin mb-2"></div>
      {text && <span className="text-xs text-slate-400">{text}</span>}
    </div>
  );
};

LoadingSpinner.displayName = 'LoadingSpinner';

export default LoadingSpinner; 