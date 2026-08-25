import { useEffect, useRef, type RefObject } from 'react';

export function getFocusable(container: HTMLElement): HTMLElement[] {
  const nodes = container.querySelectorAll<HTMLElement>(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  );
  return Array.from(nodes).filter((node) => !node.hasAttribute('disabled') && node.tabIndex !== -1);
}

export function useFocusTrap({
  open,
  containerRef,
  onEscape,
  initialFocusRef,
}: {
  open: boolean;
  containerRef: RefObject<HTMLElement | null>;
  onEscape: () => void;
  initialFocusRef?: RefObject<HTMLElement | null>;
}): void {
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    previouslyFocused.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const initial = initialFocusRef?.current ?? (containerRef.current ? getFocusable(containerRef.current)[0] : null);
    initial?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopImmediatePropagation();
        onEscape();
        return;
      }
      if (event.key !== 'Tab' || !containerRef.current) {
        return;
      }
      const focusable = getFocusable(containerRef.current);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previouslyFocused.current?.focus?.();
    };
  }, [open, onEscape, containerRef, initialFocusRef]);
}
