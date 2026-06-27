import type { StubProviderCardData } from '../../types/liveData';
import { StubProviderCard } from './StubProviderCard';

interface Props {
  data: StubProviderCardData;
}

export function TrafficCard({ data }: Props) {
  return <StubProviderCard title="Traffic ETA" data={data} />;
}
