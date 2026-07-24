import { useEffect } from 'react';
import { useLocalStorage } from './useLocalStorage';

type Theme = 'light' | 'dark';

export function useTheme(): [Theme, (theme: Theme) => void, () => void] {
  const [theme, setTheme] = useLocalStorage<Theme>('personal-ai-theme', 'dark');

  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const toggle = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  return [theme, setTheme, toggle];
}
