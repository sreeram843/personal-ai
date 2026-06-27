import type { StubProviderCardData } from '../../types/liveData';
import { StubProviderCard } from './StubProviderCard';

interface Props {
  data: StubProviderCardData;
}

export function OddsCard({ data }: Props) {
  return <StubProviderCard title="Betting odds" data={data} />;
}
