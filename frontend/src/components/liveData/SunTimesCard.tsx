import type { SunTimesCardData } from '../../types/liveData';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

function formatTime(value?: string): string {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

interface Props {
  data: SunTimesCardData;
}

export function SunTimesCard({ data }: Props) {
  return (
    <LiveDataCardChrome
      title={`Sun times — ${data.location ?? 'Unknown location'}`}
      footer={formatFreshness(data.asOf, data.source, data.confidence)}
    >
      <div className="space-y-1 text-sm text-[var(--phosphor)]">
        <div>Sunrise {formatTime(data.sunrise)}</div>
        <div>Sunset {formatTime(data.sunset)}</div>
        {data.solarNoon ? <div>Solar noon {formatTime(data.solarNoon)}</div> : null}
      </div>
    </LiveDataCardChrome>
  );
}
