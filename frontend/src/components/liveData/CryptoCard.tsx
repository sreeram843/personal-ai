import type { CryptoCardData } from '../../types/liveData';
import { useLiveBlockSubscription } from '../../hooks/useLiveBlockSubscription';
import { FreshnessBadge, LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

function formatSigned(value: number, digits = 2): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}`;
}

interface Props {
  data: CryptoCardData;
  subscriptionKey?: string | null;
}

export function CryptoCard({ data, subscriptionKey }: Props) {
  const normalized: CryptoCardData = {
    symbol: String(data.symbol ?? data.name ?? ''),
    name: String(data.name ?? data.symbol ?? ''),
    price: Number(data.price ?? 0),
    currency: String(data.currency ?? 'USD'),
    changePercent:
      data.changePercent ??
      (typeof (data as unknown as Record<string, unknown>).change_percent === 'number'
        ? ((data as unknown as Record<string, unknown>).change_percent as number)
        : undefined),
    asOf: data.asOf,
    source: data.source,
    live: data.live ?? true,
  };

  const { data: display, flash } = useLiveBlockSubscription<CryptoCardData>({
    subscriptionKey,
    initialData: normalized,
    blockType: 'crypto',
    enabled: Boolean(subscriptionKey && normalized.live),
    pollIntervalMs: 20_000,
  });

  const changePercent = typeof display.changePercent === 'number' ? display.changePercent : null;
  const positive = (changePercent ?? 0) >= 0;
  const changeClass = positive ? 'text-emerald-400' : 'text-red-400';

  return (
    <LiveDataCardChrome
      title={`${display.name} (${display.symbol})`}
      badge={<FreshnessBadge live={display.live} />}
      footer={formatFreshness(display.asOf, display.source)}
    >
      <div className={`flex items-end justify-between gap-4 ${flash ? 'live-value-flash' : ''}`}>
        <div>
          <div className="text-3xl font-semibold tabular-nums tracking-tight text-[var(--phosphor-bright)]">
            {Number(display.price).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            <span className="ml-1 text-base font-medium text-[var(--phosphor-dim)]">{display.currency}</span>
          </div>
          {changePercent !== null ? (
            <div className={`mt-1 text-sm font-medium tabular-nums ${changeClass}`}>
              {formatSigned(changePercent)}% (24h)
            </div>
          ) : null}
        </div>
      </div>
    </LiveDataCardChrome>
  );
}
