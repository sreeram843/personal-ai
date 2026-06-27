import type { StockCardData } from '../../types/liveData';
import { useLiveBlockSubscription } from '../../hooks/useLiveBlockSubscription';
import { FreshnessBadge, LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

function formatSigned(value: number, digits = 2): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}`;
}

interface Props {
  data: StockCardData;
  subscriptionKey?: string | null;
}

export function StockCard({ data, subscriptionKey }: Props) {
  const { data: display, flash } = useLiveBlockSubscription({
    subscriptionKey,
    initialData: data,
    blockType: 'stock',
    enabled: Boolean(subscriptionKey && data.live),
    pollIntervalMs: 30_000,
  });

  const change = typeof display.change === 'number' ? display.change : null;
  const changePercent = typeof display.changePercent === 'number' ? display.changePercent : null;
  const positive = (change ?? 0) >= 0;
  const changeClass = positive ? 'text-emerald-400' : 'text-red-400';

  return (
    <LiveDataCardChrome
      title={`${display.name} (${display.ticker})`}
      badge={<FreshnessBadge live={display.live} delayed={display.delayed} />}
      footer={formatFreshness(display.asOf, display.source)}
    >
      <div className={`flex items-end justify-between gap-4 ${flash ? 'live-value-flash' : ''}`}>
        <div>
          <div className="text-3xl font-semibold tabular-nums tracking-tight text-[var(--phosphor-bright)]">
            {Number(display.price).toFixed(2)}
            <span className="ml-1 text-base font-medium text-[var(--phosphor-dim)]">{display.currency}</span>
          </div>
          {change !== null && changePercent !== null ? (
            <div className={`mt-1 text-sm font-medium tabular-nums ${changeClass}`}>
              {formatSigned(change)} ({formatSigned(changePercent)}%)
            </div>
          ) : null}
        </div>
        <div className="text-right text-xs text-[var(--phosphor-dim)]">
          {display.exchange ? <div>{display.exchange}</div> : null}
          {display.marketState ? <div className="capitalize">{display.marketState}</div> : null}
          {display.previousClose != null ? <div>Prev {Number(display.previousClose).toFixed(2)}</div> : null}
        </div>
      </div>
    </LiveDataCardChrome>
  );
}
