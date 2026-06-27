import type { StubProviderCardData } from '../../types/liveData';
import { StubProviderCard } from './StubProviderCard';

interface Props {
  data: StubProviderCardData;
}

export function TransitCard({ data }: Props) {
  return <StubProviderCard title="Transit arrivals" data={data} />;
}
