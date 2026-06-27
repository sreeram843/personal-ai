import type { StubProviderCardData } from '../../types/liveData';
import { StubProviderCard } from './StubProviderCard';

interface Props {
  data: StubProviderCardData;
}

export function PackageCard({ data }: Props) {
  return <StubProviderCard title="Package tracking" data={data} />;
}
