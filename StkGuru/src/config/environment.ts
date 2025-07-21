// Environment configuration utility for StkGuru
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface AppConfig {
  apiBaseUrl: string;
  environment: string;
  appTitle: string;
  enableDebug: boolean;
  logLevel: LogLevel;
  isDevelopment: boolean;
  isProduction: boolean;
  isTest: boolean;
  isStaging: boolean;
  isGhPages: boolean;
}

// Helper to get env vars from Vite or globalThis
function getEnvVar(key: string, fallback: string = ''): string {
  // Vite env
  if (typeof import.meta !== 'undefined' && import.meta.env && key in import.meta.env) {
    return import.meta.env[key] as string;
  }
  // Vite define globals
  if (key === 'VITE_API_BASE_URL' && typeof globalThis !== 'undefined' && (globalThis as any).__API_BASE_URL__) {
    return (globalThis as any).__API_BASE_URL__;
  }
  if (key === 'VITE_ENV' && typeof globalThis !== 'undefined' && (globalThis as any).__ENV__) {
    return (globalThis as any).__ENV__;
  }
  return fallback;
}

export const config: AppConfig = {
  apiBaseUrl: getEnvVar('VITE_API_BASE_URL', 'http://localhost'),
  environment: getEnvVar('VITE_ENV', 'development'),
  appTitle: getEnvVar('VITE_APP_TITLE', 'StkGuru'),
  enableDebug: getEnvVar('VITE_ENABLE_DEBUG', 'true') === 'true',
  logLevel: (getEnvVar('VITE_LOG_LEVEL', 'debug') as LogLevel) || 'debug',
  isDevelopment: getEnvVar('VITE_ENV', 'development') === 'development',
  isProduction: getEnvVar('VITE_ENV', 'development') === 'production',
  isTest: getEnvVar('VITE_ENV', 'development') === 'test',
  isStaging: getEnvVar('VITE_ENV', 'development') === 'staging',
  isGhPages: getEnvVar('VITE_ENV', 'development') === 'ghpages',
};

// Logger utility
export const logger = {
  debug: (message: string, ...args: any[]) => {
    if (config.enableDebug && config.logLevel === 'debug') {
      // eslint-disable-next-line no-console
      console.log(`[DEBUG] ${message}`, ...args);
    }
  },
  info: (message: string, ...args: any[]) => {
    if (['debug', 'info'].includes(config.logLevel)) {
      // eslint-disable-next-line no-console
      console.info(`[INFO] ${message}`, ...args);
    }
  },
  warn: (message: string, ...args: any[]) => {
    if (['debug', 'info', 'warn'].includes(config.logLevel)) {
      // eslint-disable-next-line no-console
      console.warn(`[WARN] ${message}`, ...args);
    }
  },
  error: (message: string, ...args: any[]) => {
    // eslint-disable-next-line no-console
    console.error(`[ERROR] ${message}`, ...args);
  },
};

// API utility functions
export const apiConfig = {
  baseUrl: config.apiBaseUrl,
  // Get full API URL for a specific endpoint
  getUrl: (endpoint: string): string => {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${config.apiBaseUrl}${cleanEndpoint}`;
  },
  // Get relative API URL (for proxy in development)
  getRelativeUrl: (endpoint: string): string => {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return cleanEndpoint;
  },
  // Check if we should use relative URLs (for development proxy)
  shouldUseRelativeUrl: (): boolean => {
    return config.isDevelopment || config.isTest;
  },
  // Get the appropriate URL for API calls
  getApiUrl: (endpoint: string): string => {
    return apiConfig.shouldUseRelativeUrl()
      ? apiConfig.getRelativeUrl(endpoint)
      : apiConfig.getUrl(endpoint);
  },
};

export default config; 