import type { StubProviderCardData } from '../../types/liveData';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

interface Props {
  title: string;
  data: StubProviderCardData;
}

export function StubProviderCard({ title, data }: Props) {
  const message = data.message ?? (data.status ? data.status.replace(/_/g, ' ') : 'No data available.');
  const subtitle = data.query ? `Ref: ${data.query}` : null;

  return (
    <LiveDataCardChrome title={title} footer={formatFreshness(data.asOf, data.source, data.confidence)}>
      {subtitle ? <p className="mb-1 text-xs text-[var(--phosphor-dim)]">{subtitle}</p> : null}
      <p className="text-sm text-[var(--phosphor-dim)]">{message}</p>
    </LiveDataCardChrome>
  );
}
