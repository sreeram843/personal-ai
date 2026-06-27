import { useEffect, useRef, useState } from 'react';
import { refreshLiveBlock } from '../api';
import type { ContentBlock, CryptoCardData, GameScoreCardData, StockCardData } from '../types/liveData';

const DEFAULT_POLL_MS = 20_000;

interface Options<T> {
  subscriptionKey?: string | null;
  initialData: T;
  blockType: ContentBlock['type'];
  enabled?: boolean;
  pollIntervalMs?: number;
}

interface LiveSubscriptionState<T> {
  data: T;
  flash: boolean;
}

function scoreChanged(previous: GameScoreCardData, next: GameScoreCardData): boolean {
  if (previous.sport === 'cricket' || next.sport === 'cricket') {
    return (
      previous.homeScoreDisplay !== next.homeScoreDisplay ||
      previous.awayScoreDisplay !== next.awayScoreDisplay ||
      previous.homeScore !== next.homeScore ||
      previous.awayScore !== next.awayScore
    );
  }
  return previous.homeScore !== next.homeScore || previous.awayScore !== next.awayScore;
}

function priceChanged(previous: StockCardData | CryptoCardData, next: StockCardData | CryptoCardData): boolean {
  return previous.price !== next.price;
}

function cryptoChangeChanged(previous: CryptoCardData, next: CryptoCardData): boolean {
  return previous.changePercent !== next.changePercent;
}

function isBlockLive(
  blockType: ContentBlock['type'],
  data: GameScoreCardData | StockCardData | CryptoCardData,
): boolean {
  if (blockType === 'game_score') {
    return Boolean((data as GameScoreCardData).isLive ?? (data as GameScoreCardData).live);
  }
  if (blockType === 'stock') {
    return Boolean((data as StockCardData).live);
  }
  if (blockType === 'crypto') {
    return Boolean((data as CryptoCardData).live ?? true);
  }
  return false;
}

export function useLiveBlockSubscription<
  T extends GameScoreCardData | StockCardData | CryptoCardData,
>({
  subscriptionKey,
  initialData,
  blockType,
  enabled = true,
  pollIntervalMs = DEFAULT_POLL_MS,
}: Options<T>): LiveSubscriptionState<T> {
  const [data, setData] = useState<T>(initialData);
  const [flash, setFlash] = useState(false);
  const dataRef = useRef(data);
  dataRef.current = data;

  useEffect(() => {
    setData(initialData);
  }, [initialData]);

  const isLive = isBlockLive(blockType, data as GameScoreCardData | StockCardData | CryptoCardData);

  useEffect(() => {
    if (!enabled || !subscriptionKey || !isLive) {
      return;
    }

    let cancelled = false;

    const applyBlock = (block: ContentBlock) => {
      if (block.type !== blockType) {
        return;
      }
      const next = block.data as unknown as T;
      setData((previous) => {
        const changed =
          blockType === 'game_score'
            ? scoreChanged(previous as GameScoreCardData, next as GameScoreCardData)
            : blockType === 'stock'
              ? priceChanged(previous as StockCardData, next as StockCardData) ||
                (previous as StockCardData).change !== (next as StockCardData).change
              : blockType === 'crypto'
                ? priceChanged(previous as CryptoCardData, next as CryptoCardData) ||
                  cryptoChangeChanged(previous as CryptoCardData, next as CryptoCardData)
                : false;
        if (changed) {
          setFlash(true);
          window.setTimeout(() => setFlash(false), 900);
        }
        return next;
      });
    };

    const poll = async () => {
      if (cancelled || !isBlockLive(blockType, dataRef.current as GameScoreCardData | StockCardData | CryptoCardData)) {
        return;
      }
      try {
        const block = await refreshLiveBlock(subscriptionKey);
        if (!cancelled) {
          applyBlock(block);
        }
      } catch {
        // Ignore transient refresh failures during polling.
      }
    };

    void poll();
    const intervalId = window.setInterval(() => {
      void poll();
    }, pollIntervalMs);

    return () => {
      cancelled = true;
      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, [blockType, enabled, isLive, pollIntervalMs, subscriptionKey]);

  return { data, flash };
}
