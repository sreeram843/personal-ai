import type { NearbyPlacesCardData } from '../../types/liveData';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

interface Props {
  data: NearbyPlacesCardData;
}

export function NearbyPlacesCard({ data }: Props) {
  const label = data.categoryLabel || 'Nearby places';
  const location = data.location || 'Unknown area';
  const places = (data.places ?? []).slice(0, 12);

  return (
    <LiveDataCardChrome
      title={`${label} near ${location}`}
      footer={formatFreshness(data.asOf, data.source, data.confidence)}
    >
      <ul className="space-y-2 text-sm text-[var(--phosphor)]">
        {places.map((place, index) => (
          <li key={`${place.name ?? 'place'}-${index}`}>
            <span className="font-medium text-[var(--phosphor-bright)]">{place.name ?? 'Unnamed place'}</span>
            {place.type ? <span className="text-[var(--phosphor-dim)]"> · {place.type}</span> : null}
            {place.distanceKm != null ? (
              <span className="text-[var(--phosphor-dim)]"> · {place.distanceKm} km</span>
            ) : null}
          </li>
        ))}
        {!places.length ? <li className="text-[var(--phosphor-dim)]">No places found in this area.</li> : null}
      </ul>
    </LiveDataCardChrome>
  );
}
