import { useEffect } from 'react';
import { useLocalStorage } from './useLocalStorage';

type Theme = 'light' | 'dark';

export function useTheme(): [Theme, (theme: Theme) => void, () => void] {
  const prefersDark = typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const [theme, setTheme] = useLocalStorage<Theme>('personal-ai-theme', prefersDark ? 'dark' : 'light');

  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const toggle = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  return [theme, setTheme, toggle];
}
