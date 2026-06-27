import type { StubProviderCardData } from '../../types/liveData';
import { StubProviderCard } from './StubProviderCard';

interface Props {
  data: StubProviderCardData;
}

export function GasPriceCard({ data }: Props) {
  return <StubProviderCard title="Gas price" data={data} />;
}
