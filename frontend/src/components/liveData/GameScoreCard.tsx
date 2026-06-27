import type { GameScoreCardData } from '../../types/liveData';
import { useLiveBlockSubscription } from '../../hooks/useLiveBlockSubscription';
import { LiveDataCardChrome } from './LiveDataCardChrome';
import { formatFreshness } from '../../utils/formatFetchedAt';

interface Props {
  data: GameScoreCardData;
  subscriptionKey?: string | null;
}

export function GameScoreCard({ data, subscriptionKey }: Props) {
  const { data: display, flash } = useLiveBlockSubscription({
    subscriptionKey,
    initialData: data,
    blockType: 'game_score',
    enabled: Boolean(subscriptionKey && (data.isLive ?? data.live)),
  });

  const isCricket = display.sport === 'cricket';
  const awayLine = isCricket
    ? display.awayScoreDisplay ?? String(display.awayScore ?? '')
    : String(display.awayScore ?? 0);
  const homeLine = isCricket
    ? display.homeScoreDisplay ?? String(display.homeScore ?? '')
    : String(display.homeScore ?? 0);
  const statusLine =
    [display.matchFormat, display.period, display.clock].filter(Boolean).join(' · ') ||
    display.status;

  return (
    <LiveDataCardChrome
      title={display.league}
      badge={
        display.isLive ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/15 px-2 py-0.5 text-[11px] font-medium text-red-200">
            <span className="live-dot h-1.5 w-1.5 rounded-full bg-red-400" aria-hidden />
            Live
          </span>
        ) : (
          <span className="rounded-full bg-[var(--ui-bg)] px-2 py-0.5 text-[11px] font-medium text-[var(--phosphor-dim)]">
            {display.status}
          </span>
        )
      }
      footer={formatFreshness(display.asOf, display.source)}
    >
      <div className={`grid grid-cols-[1fr_auto_1fr] items-center gap-3 ${flash ? 'live-value-flash' : ''}`}>
        <div className="text-right">
          <div className="text-sm font-medium text-[var(--phosphor)]">{display.awayTeam}</div>
          {display.awayAbbrev ? <div className="text-xs text-[var(--phosphor-dim)]">{display.awayAbbrev}</div> : null}
        </div>
        <div className="text-center">
          <div
            className={`font-semibold tabular-nums tracking-tight text-[var(--phosphor-bright)] ${
              isCricket ? 'text-lg leading-snug' : 'text-3xl'
            }`}
          >
            {isCricket ? (
              <div className="flex flex-col gap-1">
                <span>{awayLine}</span>
                <span className="text-xs text-[var(--phosphor-dim)]">vs</span>
                <span>{homeLine}</span>
              </div>
            ) : (
              `${awayLine} – ${homeLine}`
            )}
          </div>
          <div className="mt-1 text-xs text-[var(--phosphor-dim)]">
            {isCricket && display.venue ? `${statusLine} · ${display.venue}` : statusLine}
          </div>
        </div>
        <div>
          <div className="text-sm font-medium text-[var(--phosphor)]">{display.homeTeam}</div>
          {display.homeAbbrev ? <div className="text-xs text-[var(--phosphor-dim)]">{display.homeAbbrev}</div> : null}
        </div>
      </div>
    </LiveDataCardChrome>
  );
}
