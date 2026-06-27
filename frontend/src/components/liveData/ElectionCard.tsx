import type { StubProviderCardData } from '../../types/liveData';
import { StubProviderCard } from './StubProviderCard';

interface Props {
  data: StubProviderCardData;
}

export function ElectionCard({ data }: Props) {
  return <StubProviderCard title="Election results" data={data} />;
}
