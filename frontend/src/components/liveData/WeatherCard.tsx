import type { WeatherCardData } from '../../types/liveData';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

function formatDayLabel(date?: string): string {
  if (!date) {
    return 'Day';
  }
  const parsed = new Date(`${date.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return date;
  }
  return parsed.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

interface Props {
  data: WeatherCardData;
}

export function WeatherCard({ data }: Props) {
  if (data.mode === 'forecast') {
    return (
      <LiveDataCardChrome
        title={data.location}
        badge={
          <span className="rounded-full bg-[var(--ui-bg)] px-2 py-0.5 text-[11px] font-medium text-[var(--phosphor-dim)]">
            Forecast
          </span>
        }
        footer={formatFreshness(data.asOf, data.source, data.confidence)}
      >
        <div className="space-y-2">
          {(data.days ?? []).map((day) => (
            <div
              key={`${day.date}-${day.temp_min}-${day.temp_max}`}
              className="flex items-center justify-between gap-3 rounded-lg bg-[var(--ui-bg)]/60 px-2.5 py-2 text-sm"
            >
              <span className="font-medium text-[var(--phosphor-bright)]">{formatDayLabel(day.date)}</span>
              <span className="tabular-nums text-[var(--phosphor)]">
                {day.temp_min != null && day.temp_max != null
                  ? `${Math.round(day.temp_min)}–${Math.round(day.temp_max)} ${data.tempUnit ?? '°C'}`
                  : '—'}
              </span>
            </div>
          ))}
        </div>
      </LiveDataCardChrome>
    );
  }

  return (
    <LiveDataCardChrome
      title={data.location}
      badge={
        <span className="rounded-full bg-[var(--ui-bg)] px-2 py-0.5 text-[11px] font-medium text-[var(--phosphor-dim)]">
          Current
        </span>
      }
      footer={formatFreshness(data.asOf, data.source, data.confidence)}
    >
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-3xl font-semibold tabular-nums tracking-tight text-[var(--phosphor-bright)]">
            {data.temperature != null ? Math.round(Number(data.temperature)) : '—'}
            <span className="ml-1 text-base font-medium text-[var(--phosphor-dim)]">
              {data.temperatureUnit ?? '°C'}
            </span>
          </div>
          <div className="mt-1 text-sm text-[var(--phosphor)]">{data.condition ?? 'Unknown'}</div>
        </div>
        <div className="text-right text-xs leading-relaxed text-[var(--phosphor-dim)]">
          {data.feelsLike != null ? <div>Feels {Math.round(Number(data.feelsLike))}{data.temperatureUnit ?? '°C'}</div> : null}
          {data.humidity != null ? <div>Humidity {data.humidity}{data.humidityUnit ?? '%'}</div> : null}
          {data.windSpeed != null ? (
            <div>
              Wind {data.windSpeed} {data.windSpeedUnit ?? 'km/h'}
            </div>
          ) : null}
        </div>
      </div>
    </LiveDataCardChrome>
  );
}
