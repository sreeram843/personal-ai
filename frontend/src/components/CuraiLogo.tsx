import { clsx } from 'clsx';
import { useEffect, useId, useState } from 'react';
import {
  curaiLogoStateLabels,
  type CuraiLogoState,
} from './curaiLogoState';

export type { CuraiLogoState } from './curaiLogoState';

interface CuraiLogoProps {
  state?: CuraiLogoState;
  size?: number;
  className?: string;
  title?: string;
}

function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onChange = () => setPrefersReducedMotion(mediaQuery.matches);
    mediaQuery.addEventListener('change', onChange);
    return () => mediaQuery.removeEventListener('change', onChange);
  }, []);

  return prefersReducedMotion;
}

const CX = 64;
const CY = 64;
const ORBIT_RX = 18;
const ORBIT_RY = 46;

const BULB_GLASS =
  'M64 32 C49 32 41 42 41 55 C41 63 44 69 49 74 L50 80 C50 84 54 86 64 86 C74 86 78 84 78 80 L79 74 C84 69 87 63 87 55 C87 42 79 32 64 32 Z';
const BULB_BASE = 'M57 86 L56 93 C56 95 59 96 64 96 C69 96 72 95 72 93 L71 86 Z';
const BULB_FILAMENT = 'M57.5 51 C57.5 57.5 60.5 61 64 61 C67.5 61 70.5 57.5 70.5 51';
const BULB_THREADS = [
  'M58 88.2 Q64 88.45 70 88.2',
  'M58 90 Q64 90.25 70 90',
  'M58 91.8 Q64 92.05 70 91.8',
] as const;
const BULB_CENTER_Y = 62;
const BULB_SCALE = 0.84;

/** Closed ellipse path for animateMotion (clockwise). */
const ORBIT_PATH_CW = `M ${CX} ${CY + ORBIT_RY} A ${ORBIT_RX} ${ORBIT_RY} 0 1 1 ${CX} ${CY - ORBIT_RY} A ${ORBIT_RX} ${ORBIT_RY} 0 1 1 ${CX} ${CY + ORBIT_RY}`;
const ORBIT_PATH_CCW = `M ${CX} ${CY - ORBIT_RY} A ${ORBIT_RX} ${ORBIT_RY} 0 1 0 ${CX} ${CY + ORBIT_RY} A ${ORBIT_RX} ${ORBIT_RY} 0 1 0 ${CX} ${CY - ORBIT_RY}`;

const ORBIT_CONFIG = [
  { rotate: 0, path: ORBIT_PATH_CW, duration: '5.5s', begin: '0s', idleX: CX, idleY: CY + ORBIT_RY },
  { rotate: -60, path: ORBIT_PATH_CCW, duration: '7s', begin: '-1.2s', idleX: CX, idleY: CY - ORBIT_RY },
  { rotate: 60, path: ORBIT_PATH_CW, duration: '4.2s', begin: '-0.6s', idleX: CX + ORBIT_RX, idleY: CY },
] as const;

interface OrbitingElectronProps {
  orbit: (typeof ORBIT_CONFIG)[number];
  animate: boolean;
  motionClassName: string;
}

function OrbitingElectron({ orbit, animate, motionClassName }: OrbitingElectronProps) {
  const electron = (
    <circle className="curai-logo__electron" r="3.75">
      {animate ? (
        <animateMotion
          className={motionClassName}
          dur={orbit.duration}
          begin={orbit.begin}
          repeatCount="indefinite"
          path={orbit.path}
        />
      ) : null}
    </circle>
  );

  if (animate) {
    return <g transform={`rotate(${orbit.rotate} ${CX} ${CY})`}>{electron}</g>;
  }

  const rad = (orbit.rotate * Math.PI) / 180;
  const localX = orbit.idleX - CX;
  const localY = orbit.idleY - CY;
  const x = CX + localX * Math.cos(rad) - localY * Math.sin(rad);
  const y = CY + localX * Math.sin(rad) + localY * Math.cos(rad);

  return <circle className="curai-logo__electron" cx={x} cy={y} r="3.75" />;
}

function CuraiLogoMark({
  gradientId,
  animateElectrons,
}: {
  gradientId: string;
  animateElectrons: boolean;
}) {
  return (
    <svg viewBox="0 0 128 128" className="curai-logo__svg h-full w-full" aria-hidden focusable="false">
      <defs>
        <radialGradient id={gradientId} cx="50%" cy="36%" r="58%" fx="50%" fy="34%">
          <stop offset="0%" stopColor="#FFF9C4" />
          <stop offset="32%" stopColor="#FFE566" />
          <stop offset="68%" stopColor="#F5B82E" />
          <stop offset="100%" stopColor="#E8A020" />
        </radialGradient>
      </defs>

      <g className="curai-logo__bulb-pulse">
        <g
          className="curai-logo__bulb"
          transform={`translate(${CX} ${BULB_CENTER_Y}) scale(${BULB_SCALE}) translate(${-CX} ${-BULB_CENTER_Y})`}
        >
          <path className="curai-logo__bulb-glass" d={BULB_GLASS} fill={`url(#${gradientId})`} />
          <path className="curai-logo__bulb-stroke" d={BULB_GLASS} fill="none" />
          <path className="curai-logo__filament" d={BULB_FILAMENT} fill="none" />
          <path className="curai-logo__bulb-base" d={BULB_BASE} />
          {BULB_THREADS.map((thread) => (
            <path key={thread} className="curai-logo__bulb-thread" d={thread} fill="none" />
          ))}
        </g>
      </g>

      {ORBIT_CONFIG.map((orbit) => (
        <ellipse
          key={`ring-${orbit.rotate}`}
          className="curai-logo__orbit"
          cx={CX}
          cy={CY}
          rx={ORBIT_RX}
          ry={ORBIT_RY}
          transform={`rotate(${orbit.rotate} ${CX} ${CY})`}
        />
      ))}

      {ORBIT_CONFIG.map((orbit) => (
        <OrbitingElectron
          key={`electron-${orbit.rotate}`}
          orbit={orbit}
          animate={animateElectrons}
          motionClassName="curai-logo__electron-motion"
        />
      ))}
    </svg>
  );
}

/** CurAI mark — SVG bulb behind orbits; electrons travel fixed paths. */
export function CuraiLogo({ state = 'idle', size = 32, className, title }: CuraiLogoProps) {
  const gradientId = `curai-bulb-${useId().replace(/:/g, '')}`;
  const prefersReducedMotion = usePrefersReducedMotion();
  const animateElectrons =
    !prefersReducedMotion && (state === 'thinking' || state === 'active');

  return (
    <span
      role="img"
      aria-label={title ?? curaiLogoStateLabels[state]}
      data-state={state}
      className={clsx('curai-logo inline-flex shrink-0 items-center justify-center', className)}
      style={{ width: size, height: size }}
    >
      <span className="curai-logo__stage">
        <CuraiLogoMark gradientId={gradientId} animateElectrons={animateElectrons} />
      </span>
    </span>
  );
}
