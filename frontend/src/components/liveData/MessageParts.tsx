import type { ComponentType } from 'react';
import type {
  AirQualityCardData,
  CommodityCardData,
  ContentBlockType,
  FlightCardData,
  FxCardData,
  GameScoreCardData,
  MessagePart,
  NearbyPlacesCardData,
  NewsCardData,
  ServiceStatusCardData,
  StockCardData,
  StubProviderCardData,
  SunTimesCardData,
  WeatherCardData,
} from '../../types/liveData';
import { AirQualityCard } from './AirQualityCard';
import { CommodityCard } from './CommodityCard';
import { CryptoCard } from './CryptoCard';
import { ElectionCard } from './ElectionCard';
import { FlightCard } from './FlightCard';
import { FxCard } from './FxCard';
import { GameScoreCard } from './GameScoreCard';
import { GasPriceCard } from './GasPriceCard';
import { NewsCard } from './NewsCard';
import { NearbyPlacesCard } from './NearbyPlacesCard';
import { OddsCard } from './OddsCard';
import { PackageCard } from './PackageCard';
import { ServiceStatusCard } from './ServiceStatusCard';
import { StockCard } from './StockCard';
import { SunTimesCard } from './SunTimesCard';
import { TrafficCard } from './TrafficCard';
import { TransitCard } from './TransitCard';
import { WeatherCard } from './WeatherCard';
import { MessageContent } from '../MessageContent';

type CardComponentProps = {
  data: Record<string, unknown>;
  subscriptionKey?: string | null;
};

const CARD_REGISTRY: Partial<Record<ContentBlockType, ComponentType<CardComponentProps>>> = {
  stock: ({ data, subscriptionKey }) => (
    <StockCard data={data as unknown as StockCardData} subscriptionKey={subscriptionKey} />
  ),
  crypto: ({ data, subscriptionKey }) => (
    <CryptoCard data={data as unknown as import('../../types/liveData').CryptoCardData} subscriptionKey={subscriptionKey} />
  ),
  weather: ({ data }) => <WeatherCard data={data as unknown as WeatherCardData} />,
  game_score: ({ data, subscriptionKey }) => (
    <GameScoreCard data={data as unknown as GameScoreCardData} subscriptionKey={subscriptionKey} />
  ),
  fx: ({ data }) => <FxCard data={data as unknown as FxCardData} />,
  news: ({ data }) => <NewsCard data={data as unknown as NewsCardData} />,
  nearby_places: ({ data }) => <NearbyPlacesCard data={data as unknown as NearbyPlacesCardData} />,
  air_quality: ({ data }) => <AirQualityCard data={data as unknown as AirQualityCardData} />,
  service_status: ({ data }) => <ServiceStatusCard data={data as unknown as ServiceStatusCardData} />,
  flight: ({ data }) => <FlightCard data={data as unknown as FlightCardData} />,
  commodity: ({ data }) => <CommodityCard data={data as unknown as CommodityCardData} />,
  sun_times: ({ data }) => <SunTimesCard data={data as unknown as SunTimesCardData} />,
  package: ({ data }) => <PackageCard data={data as unknown as StubProviderCardData} />,
  transit: ({ data }) => <TransitCard data={data as unknown as StubProviderCardData} />,
  traffic: ({ data }) => <TrafficCard data={data as unknown as StubProviderCardData} />,
  gas_price: ({ data }) => <GasPriceCard data={data as unknown as StubProviderCardData} />,
  odds: ({ data }) => <OddsCard data={data as unknown as StubProviderCardData} />,
  election: ({ data }) => <ElectionCard data={data as unknown as StubProviderCardData} />,
};

interface Props {
  part: MessagePart;
}

export function ContentPart({ part }: Props) {
  if (part.kind === 'text') {
    return <MessageContent content={part.text} />;
  }

  const Card = CARD_REGISTRY[part.type];
  if (Card) {
    return <Card data={part.data} subscriptionKey={part.subscriptionKey} />;
  }

  return null;
}

interface ListProps {
  parts: MessagePart[];
  showStreamingCaret?: boolean;
}

export function MessageParts({ parts, showStreamingCaret }: ListProps) {
  if (!parts.length) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2.5">
      {parts.map((part, index) => {
        const key = part.kind === 'card' ? `card-${part.type}-${part.subscriptionKey ?? index}` : `text-${index}`;
        if (part.kind === 'text') {
          return (
            <div key={key} className="inline">
              <ContentPart part={part} />
              {showStreamingCaret ? <span className="stream-caret" aria-hidden /> : null}
            </div>
          );
        }
        return (
          <div key={key}>
            <ContentPart part={part} />
          </div>
        );
      })}
    </div>
  );
}
