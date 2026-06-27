import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';

const NEAR_BOTTOM_THRESHOLD_PX = 80;

export function useMessageLogScroll(
  containerRef: RefObject<HTMLElement | null>,
  scrollDeps: unknown[],
) {
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const stickToBottomRef = useRef(true);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const onScroll = () => {
      const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      const nearBottom = distanceFromBottom <= NEAR_BOTTOM_THRESHOLD_PX;
      stickToBottomRef.current = nearBottom;
      setIsNearBottom(nearBottom);
      setShowJumpToLatest(!nearBottom);
    };

    container.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => container.removeEventListener('scroll', onScroll);
  }, [containerRef]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !stickToBottomRef.current) {
      return;
    }

    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- explicit scroll triggers only
  }, scrollDeps);

  const jumpToLatest = useCallback(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
    stickToBottomRef.current = true;
    setIsNearBottom(true);
    setShowJumpToLatest(false);
  }, [containerRef]);

  return { showJumpToLatest, jumpToLatest, isNearBottom };
}
