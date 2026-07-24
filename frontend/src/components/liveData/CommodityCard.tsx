import type { CommodityCardData } from '../../types/liveData';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

interface Props {
  data: CommodityCardData;
}

export function CommodityCard({ data }: Props) {
  const label = data.name ?? data.ticker ?? 'Commodity';
  const price = data.price != null ? Number(data.price).toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—';

  return (
    <LiveDataCardChrome title={label} footer={formatFreshness(data.asOf, data.source, data.confidence)}>
      <div className="text-3xl font-semibold tabular-nums tracking-tight text-[var(--phosphor-bright)]">
        {price}
        <span className="ml-1 text-base font-medium text-[var(--phosphor-dim)]">{data.currency ?? 'USD'}</span>
      </div>
      {data.ticker ? <div className="mt-1 text-xs text-[var(--phosphor-dim)]">{data.ticker}</div> : null}
    </LiveDataCardChrome>
  );
}
