import type { FlightCardData } from '../../types/liveData';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

interface Props {
  data: FlightCardData;
}

export function FlightCard({ data }: Props) {
  const title = data.query ? `Flight ${data.query}` : 'Flight status';
  const message = data.message ?? data.status ?? 'No flight data available.';

  return (
    <LiveDataCardChrome title={title} footer={formatFreshness(data.asOf, data.source)}>
      <p className="text-sm text-[var(--phosphor-dim)]">{message}</p>
    </LiveDataCardChrome>
  );
}
