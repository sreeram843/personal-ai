export type ContentBlockType =
  | 'stock'
  | 'weather'
  | 'game_score'
  | 'crypto'
  | 'fx'
  | 'commodity'
  | 'flight'
  | 'transit'
  | 'traffic'
  | 'package'
  | 'air_quality'
  | 'service_status'
  | 'sun_times'
  | 'gas_price'
  | 'odds'
  | 'election'
  | 'news'
  | 'text';

export interface ContentBlock {
  type: ContentBlockType;
  data: Record<string, unknown>;
  subscription_key?: string | null;
}

export type MessagePart =
  | { kind: 'text'; text: string }
  | { kind: 'card'; type: ContentBlockType; data: Record<string, unknown>; subscriptionKey?: string | null };

export interface StockCardData {
  ticker: string;
  name: string;
  price: number;
  currency: string;
  change?: number | null;
  changePercent?: number | null;
  previousClose?: number | null;
  exchange?: string;
  marketState?: string;
  delayed?: boolean;
  asOf?: string;
  source?: string;
  live?: boolean;
}

export interface CryptoCardData {
  symbol: string;
  name: string;
  price: number;
  currency: string;
  changePercent?: number | null;
  asOf?: string;
  source?: string;
  live?: boolean;
}

export interface WeatherDayForecast {
  date?: string;
  code?: number;
  temp_min?: number;
  temp_max?: number;
  precip?: number;
  wind_max?: number;
}

export interface WeatherCardData {
  mode: 'current' | 'forecast';
  location: string;
  condition?: string;
  temperature?: number;
  temperatureUnit?: string;
  feelsLike?: number;
  humidity?: number;
  humidityUnit?: string;
  windSpeed?: number;
  windSpeedUnit?: string;
  precipitation?: number;
  precipitationUnit?: string;
  days?: WeatherDayForecast[];
  tempUnit?: string;
  precipUnit?: string;
  windUnit?: string;
  asOf?: string;
  source?: string;
  live?: boolean;
}

export interface GameScoreCardData {
  league: string;
  homeTeam: string;
  awayTeam: string;
  homeAbbrev?: string;
  awayAbbrev?: string;
  homeScore: number;
  awayScore: number;
  homeScoreDisplay?: string;
  awayScoreDisplay?: string;
  sport?: 'cricket' | 'default' | string;
  matchFormat?: string;
  venue?: string;
  status: string;
  period?: string;
  clock?: string;
  isLive?: boolean;
  live?: boolean;
  asOf?: string;
  source?: string;
}

export interface FxCardData {
  base?: string;
  quote?: string;
  rate?: number | null;
  date?: string;
  asOf?: string;
  source?: string;
  live?: boolean;
}

export interface NewsHeadline {
  title?: string;
  source?: string;
  url?: string;
}

export interface NewsCardData {
  topic?: string;
  headlines?: NewsHeadline[];
  asOf?: string;
  source?: string;
  live?: boolean;
}

export interface AirQualityCardData {
  location?: string;
  usAqi?: number | string | null;
  pm25?: number | string | null;
  pm10?: number | string | null;
  asOf?: string;
  source?: string;
  live?: boolean;
}

export interface ServiceStatusCardData {
  service?: string;
  status?: string;
  description?: string;
  asOf?: string;
  source?: string;
  live?: boolean;
}

export interface FlightCardData {
  query?: string;
  status?: string;
  message?: string;
  asOf?: string;
  source?: string;
  live?: boolean;
}

export interface CommodityCardData {
  ticker?: string;
  name?: string;
  price?: number | null;
  currency?: string;
  asOf?: string;
  source?: string;
  live?: boolean;
}

export interface SunTimesCardData {
  location?: string;
  sunrise?: string;
  sunset?: string;
  solarNoon?: string;
  dayLengthSeconds?: number;
  asOf?: string;
  source?: string;
  live?: boolean;
}

export interface StubProviderCardData {
  query?: string;
  status?: string;
  message?: string;
  kind?: string;
  asOf?: string;
  source?: string;
  live?: boolean;
}
