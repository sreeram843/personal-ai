import { Capacitor } from '@capacitor/core';

export function isCapacitorNative(): boolean {
  return Capacitor.isNativePlatform();
}

export function getCapacitorPlatform(): 'ios' | 'android' | 'web' {
  return Capacitor.getPlatform() as 'ios' | 'android' | 'web';
}

export async function initCapacitorShell(): Promise<void> {
  if (!isCapacitorNative()) {
    return;
  }

  const [{ App }, { SplashScreen }, { StatusBar, Style }] = await Promise.all([
    import('@capacitor/app'),
    import('@capacitor/splash-screen'),
    import('@capacitor/status-bar'),
  ]);

  if (getCapacitorPlatform() === 'android') {
    await StatusBar.setStyle({ style: Style.Dark });
  }

  document.documentElement.classList.add('capacitor-native');

  void App.addListener('backButton', ({ canGoBack }) => {
    if (canGoBack) {
      window.history.back();
      return;
    }
    void App.exitApp();
  });

  await SplashScreen.hide();
}
