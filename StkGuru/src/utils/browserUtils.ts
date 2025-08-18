// Browser utility functions to handle Chrome extension issues

export const detectProblematicExtensions = (): string[] => {
  const problematicExtensions: string[] = [];
  
  // Check for common problematic extensions
  // const extensions = [
  //   'chrome-extension://',
  //   'moz-extension://',
  //   'safari-extension://'
  // ];
  
  // Check if any chrome-extension URLs are being cached
  if ('caches' in window) {
    try {
      // This will help identify if there are extension-related cache issues
      caches.open('test');
    } catch (error) {
      if (error instanceof Error && error.message.includes('chrome-extension')) {
        problematicExtensions.push('Cache Extension');
      }
    }
  }
  
  return problematicExtensions;
};

export const clearExtensionInterference = async (): Promise<void> => {
  // Clear any extension-related caches
  if ('caches' in window) {
    try {
      const cacheNames = await caches.keys();
      const extensionCaches = cacheNames.filter(name => 
        name.includes('extension') || name.includes('chrome-extension')
      );
      
      await Promise.all(
        extensionCaches.map(name => caches.delete(name))
      );
    } catch (error) {
      // Ignore cache clearing errors

    }
  }
  
  // Unregister problematic service workers
  if ('serviceWorker' in navigator) {
    try {
      const registrations = await navigator.serviceWorker.getRegistrations();
      const extensionWorkers = registrations.filter(registration =>
        registration.scope.includes('chrome-extension') ||
        registration.scope.includes('moz-extension')
      );
      
      await Promise.all(
        extensionWorkers.map(registration => registration.unregister())
      );
    } catch (error) {
      // Ignore service worker errors

    }
  }
};

export const isIncognitoMode = (): boolean => {
  // Simple incognito detection
  try {
    const test = 'test';
    localStorage.setItem(test, test);
    localStorage.removeItem(test);
    return false;
  } catch (e) {
    return true;
  }
};

export const getBrowserInfo = () => {
  const userAgent = navigator.userAgent;
  const isChrome = /Chrome/.test(userAgent) && !/Edge/.test(userAgent);
  const isSafari = /Safari/.test(userAgent) && !/Chrome/.test(userAgent);
  const isFirefox = /Firefox/.test(userAgent);
  
  return {
    isChrome,
    isSafari,
    isFirefox,
    isIncognito: isIncognitoMode(),
    userAgent
  };
};

export const shouldShowExtensionWarning = (): boolean => {
  const browserInfo = getBrowserInfo();
  return browserInfo.isChrome && !browserInfo.isIncognito;
}; 