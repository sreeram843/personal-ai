import type { FxCardData } from '../../types/liveData';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

interface Props {
  data: FxCardData;
}

export function FxCard({ data }: Props) {
  const rate = data.rate != null ? Number(data.rate).toFixed(4) : '—';

  return (
    <LiveDataCardChrome title="Exchange rate" footer={formatFreshness(data.asOf, data.source, data.confidence)}>
      <div className="text-2xl font-semibold tabular-nums text-[var(--phosphor-bright)]">
        1 {data.base ?? ''} = {rate} {data.quote ?? ''}
      </div>
      {data.date ? <div className="mt-1 text-xs text-[var(--phosphor-dim)]">Rate date {data.date}</div> : null}
    </LiveDataCardChrome>
  );
}
