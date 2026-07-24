import type { NewsCardData } from '../../types/liveData';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

interface Props {
  data: NewsCardData;
}

export function NewsCard({ data }: Props) {
  const topic = data.topic || 'News';
  const headlines = (data.headlines ?? []).slice(0, 5);

  return (
    <LiveDataCardChrome title={`Latest on ${topic}`} footer={formatFreshness(data.asOf, data.source, data.confidence)}>
      <ul className="space-y-2 text-sm text-[var(--phosphor)]">
        {headlines.map((item, index) => (
          <li key={`${item.title ?? 'item'}-${index}`}>
            <span className="font-medium text-[var(--phosphor-bright)]">{item.title ?? 'Untitled'}</span>
            {item.source ? <span className="text-[var(--phosphor-dim)]"> — {item.source}</span> : null}
          </li>
        ))}
        {!headlines.length ? <li className="text-[var(--phosphor-dim)]">No headlines available.</li> : null}
      </ul>
    </LiveDataCardChrome>
  );
}
