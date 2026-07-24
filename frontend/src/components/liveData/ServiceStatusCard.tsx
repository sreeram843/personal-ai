import type { ServiceStatusCardData } from '../../types/liveData';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

interface Props {
  data: ServiceStatusCardData;
}

export function ServiceStatusCard({ data }: Props) {
  const label = data.service ? `${data.service} status` : 'Service status';
  const description = data.description ?? data.status ?? 'Unknown';

  return (
    <LiveDataCardChrome title={label} footer={formatFreshness(data.asOf, data.source, data.confidence)}>
      <div className="text-lg font-medium capitalize text-[var(--phosphor-bright)]">{description}</div>
    </LiveDataCardChrome>
  );
}
