import { useEffect, useState } from 'react';
import type { ThemeMode } from './palette';

/** Track the `dark` class on <html>, kept in sync with the theme toggle. */
export function useThemeMode(): ThemeMode {
  const [mode, setMode] = useState<ThemeMode>('light');

  useEffect(() => {
    const root = document.documentElement;
    const read = () => setMode(root.classList.contains('dark') ? 'dark' : 'light');
    read();
    const observer = new MutationObserver(read);
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  return mode;
}
