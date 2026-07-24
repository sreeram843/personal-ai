import type { AirQualityCardData } from '../../types/liveData';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

interface Props {
  data: AirQualityCardData;
}

export function AirQualityCard({ data }: Props) {
  return (
    <LiveDataCardChrome
      title={`Air quality — ${data.location ?? 'Unknown location'}`}
      footer={formatFreshness(data.asOf, data.source, data.confidence)}
    >
      <div className="text-2xl font-semibold tabular-nums text-[var(--phosphor-bright)]">
        US AQI {data.usAqi ?? '—'}
      </div>
      <div className="mt-1 text-sm text-[var(--phosphor-dim)]">
        PM2.5 {data.pm25 ?? '—'} · PM10 {data.pm10 ?? '—'}
      </div>
    </LiveDataCardChrome>
  );
}
