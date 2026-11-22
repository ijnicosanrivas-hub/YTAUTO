/**
 * Ilustraciones vectoriales de cada canal (cabeceras y tarjetas): Gotham de noche con la batseñal, Vice City al
 * atardecer, el cielo arcoíris de Kids y el estadio iluminado de Deportes. SVG propio: ligero y sin descargas.
 */
import { useId } from "react";

function rnd(i: number): number {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

function Skyline({ y, color, seed, count = 34, maxH = 120, w = 1200, deco = false }: { y: number; color: string; seed: number; count?: number; maxH?: number; w?: number; deco?: boolean }) {
  const step = w / count;
  return (
    <g fill={color}>
      {[...Array(count)].map((_, i) => {
        const h = 30 + rnd(i + seed) * maxH;
        const bw = step * (0.7 + rnd(i * 3 + seed) * 0.5);
        const x = i * step;
        return (
          <g key={i}>
            <rect x={x} y={y - h} width={bw} height={h + 40} />
            {deco && rnd(i * 7 + seed) > 0.7 && <path d={`M${x + bw / 2 - 6} ${y - h} L${x + bw / 2} ${y - h - 30} L${x + bw / 2 + 6} ${y - h} Z`} />}
          </g>
        );
      })}
    </g>
  );
}

function Windows({ y, seed, color, count = 34, w = 1200 }: { y: number; seed: number; color: string; count?: number; w?: number }) {
  const step = w / count;
  const out = [];
  for (let i = 0; i < count; i++) {
    const h = 30 + rnd(i + seed) * 120;
    for (let k = 0; k < 6; k++) {
      if (rnd(i * 13 + k + seed) > 0.62) out.push(<rect key={`${i}-${k}`} x={i * step + 4 + (k % 2) * 8} y={y - h + 8 + Math.floor(k / 2) * 14} width="4" height="6" />);
    }
  }
  return <g fill={color} opacity="0.85">{out}</g>;
}

function Gotham({ id }: { id: string }) {
  return (
    <>
      <defs>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#050812" /><stop offset="0.7" stopColor="#1b2438" /><stop offset="1" stopColor="#2c3247" /></linearGradient>
        <linearGradient id={`${id}b`} x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor="#ffe066" stopOpacity="0.55" /><stop offset="1" stopColor="#ffe066" stopOpacity="0" /></linearGradient>
        <radialGradient id={`${id}m`}><stop offset="0" stopColor="#fff7c2" /><stop offset="1" stopColor="#ffd400" /></radialGradient>
      </defs>
      <rect width="1200" height="300" fill={`url(#${id}s)`} />
      {[...Array(40)].map((_, i) => <circle key={i} cx={rnd(i) * 1200} cy={rnd(i + 50) * 150} r={rnd(i + 9) * 1.4 + 0.3} fill="#dbe4ff" opacity={0.4 + rnd(i + 3) * 0.5} />)}
      <polygon points="760,300 900,52 1040,52 860,300" fill={`url(#${id}b)`} />
      <ellipse cx="970" cy="64" rx="86" ry="44" fill={`url(#${id}m)`} opacity="0.95" />
      <path d="M970 50 c-8 -2 -14 6 -22 4 c-6 -2 -10 -10 -10 -10 c-4 8 -10 10 -20 10 c-12 0 -20 -12 -20 -12 c0 10 6 24 22 28 c8 2 14 -2 18 -8 c4 4 8 10 12 10 c4 0 8 -6 12 -10 c4 6 10 10 18 8 c16 -4 22 -18 22 -28 c0 0 -8 12 -20 12 c-10 0 -16 -2 -20 -10 c0 0 -4 8 -10 10 c-8 2 -14 -6 -22 -4 z" fill="#0b0d12" transform="translate(-8 4)" />
      <Skyline y={250} color="#0e1422" seed={3} count={26} maxH={150} deco />
      <Windows y={250} seed={3} color="#ffd86b" count={26} />
      <Skyline y={280} color="#070a12" seed={9} count={40} maxH={90} deco />
      <rect y="278" width="1200" height="30" fill="#05070c" />
    </>
  );
}

function Palm({ x, y, s = 1, flip = false, color }: { x: number; y: number; s?: number; flip?: boolean; color: string }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${flip ? -s : s} ${s})`} fill={color}>
      <path d="M0 0 C 6 -40 14 -80 30 -120 L 36 -118 C 22 -80 14 -40 8 0 Z" />
      {[-60, -25, 10, 40, 75, 120, 160].map((a, i) => (
        <path key={i} d="M33 -120 q 30 -20 70 -6 q -38 -2 -70 12 z" transform={`rotate(${a} 33 -120)`} />
      ))}
    </g>
  );
}

function Vice({ id }: { id: string }) {
  return (
    <>
      <defs>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1a0b3a" /><stop offset="0.45" stopColor="#7a1fa2" /><stop offset="0.72" stopColor="#ff4fa3" /><stop offset="0.9" stopColor="#ffb15c" />
        </linearGradient>
        <linearGradient id={`${id}u`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff3a0" /><stop offset="0.55" stopColor="#ff9f43" /><stop offset="1" stopColor="#ff2f8e" /></linearGradient>
        <linearGradient id={`${id}o`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3b1d6e" /><stop offset="1" stopColor="#120726" /></linearGradient>
        <mask id={`${id}k`}><rect width="1200" height="300" fill="#fff" />{[...Array(7)].map((_, i) => <rect key={i} x="0" y={150 + i * 13} width="1200" height={2 + i * 1.3} fill="#000" />)}</mask>
      </defs>
      <rect width="1200" height="300" fill={`url(#${id}s)`} />
      <circle cx="760" cy="200" r="120" fill={`url(#${id}u)`} mask={`url(#${id}k)`} />
      <Skyline y={222} color="#2a0f4a" seed={21} count={44} maxH={80} />
      <Windows y={222} seed={21} color="#ff9fd6" count={44} />
      <rect y="220" width="1200" height="80" fill={`url(#${id}o)`} />
      {[...Array(9)].map((_, i) => <rect key={i} x={600 + Math.sin(i) * 60} y={232 + i * 7} width={200 - i * 14} height="2" fill="#ff8fd0" opacity={0.6 - i * 0.05} />)}
      <Palm x={90} y={300} s={1.5} color="#12061f" />
      <Palm x={170} y={300} s={1.1} flip color="#12061f" />
      <Palm x={1120} y={300} s={1.6} flip color="#12061f" />
      <Palm x={1040} y={300} s={1.05} color="#12061f" />
    </>
  );
}

function Kids({ id }: { id: string }) {
  const rainbow = ["#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#00c7be", "#007aff", "#af52de"];
  return (
    <>
      <defs>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#5ab8ff" /><stop offset="1" stopColor="#d8f1ff" /></linearGradient>
      </defs>
      <rect width="1200" height="300" fill={`url(#${id}s)`} />
      <g transform="translate(1050 70)">
        {[...Array(12)].map((_, i) => <rect key={i} x="-6" y="-78" width="12" height="26" rx="6" fill="#ffb703" transform={`rotate(${i * 30})`} />)}
        <circle r="44" fill="#ffd60a" />
        <circle cx="-14" cy="-6" r="5" fill="#5a3d00" /><circle cx="14" cy="-6" r="5" fill="#5a3d00" />
        <path d="M-16 10 q16 16 32 0" stroke="#5a3d00" strokeWidth="5" fill="none" strokeLinecap="round" />
      </g>
      {rainbow.map((c, i) => <path key={c} d={`M${250 + i * 18} 300 A ${300 - i * 18} ${250 - i * 18} 0 0 1 ${850 - i * 18} 300`} stroke={c} strokeWidth="18" fill="none" />)}
      {[[160, 80, 1], [520, 60, 1.3], [880, 120, 0.9]].map(([x, y, s], i) => (
        <g key={i} transform={`translate(${x} ${y}) scale(${s})`} fill="#fff">
          <circle r="34" /><circle cx="40" cy="8" r="28" /><circle cx="-40" cy="10" r="26" /><circle cx="10" cy="-22" r="26" />
        </g>
      ))}
      <path d="M0 260 Q 200 200 420 250 T 820 240 T 1200 250 V300 H0Z" fill="#7ed957" />
      <path d="M0 280 Q 260 240 560 275 T 1200 270 V300 H0Z" fill="#5cc93c" />
      {[["#ff3b30", 300, 150], ["#007aff", 340, 170], ["#ffcc00", 950, 160], ["#af52de", 990, 180]].map(([c, x, y], i) => (
        <g key={i}><path d={`M${x} ${Number(y) + 36} q 6 30 -4 60`} stroke="#fff" strokeWidth="2" fill="none" /><ellipse cx={x} cy={y} rx="24" ry="30" fill={c as string} /><ellipse cx={Number(x) - 8} cy={Number(y) - 10} rx="6" ry="9" fill="#fff" opacity="0.5" /></g>
      ))}
    </>
  );
}

function Stadium({ id }: { id: string }) {
  return (
    <>
      <defs>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#020604" /><stop offset="0.6" stopColor="#0b2a17" /><stop offset="1" stopColor="#0f3d20" /></linearGradient>
        <linearGradient id={`${id}l`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fffbe6" stopOpacity="0.5" /><stop offset="1" stopColor="#fffbe6" stopOpacity="0" /></linearGradient>
        <linearGradient id={`${id}p`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2f8f44" /><stop offset="1" stopColor="#1f6b31" /></linearGradient>
      </defs>
      <rect width="1200" height="300" fill={`url(#${id}s)`} />
      {[120, 1080].map((x) => (
        <g key={x}>
          <polygon points={`${x - 30},40 ${x + 30},40 ${x === 120 ? 700 : 500},300 ${x === 120 ? 300 : 900},300`} fill={`url(#${id}l)`} />
          <rect x={x - 34} y="22" width="68" height="26" rx="4" fill="#1f2937" />
          {[...Array(8)].map((_, i) => <circle key={i} cx={x - 25 + (i % 4) * 17} cy={29 + Math.floor(i / 4) * 12} r="5" fill="#fffbe6" />)}
        </g>
      ))}
      <path d="M0 150 L1200 150 L1200 205 L0 205Z" fill="#111827" />
      {[...Array(120)].map((_, i) => <circle key={i} cx={(i % 60) * 20 + 10 + (i > 59 ? 10 : 0)} cy={i > 59 ? 186 : 168} r="6" fill={["#e11d48", "#f8fafc", "#1d4ed8", "#facc15", "#16a34a"][Math.floor(rnd(i) * 5)]} opacity="0.9" />)}
      <rect y="203" width="1200" height="14" fill="#0ea5e9" />
      <text x="600" y="214" textAnchor="middle" fontFamily="Oswald, Impact, sans-serif" fontSize="12" fontWeight="700" fill="#fff" letterSpacing="6">YTAUTO · SHORTS · REELS · TIKTOK · YTAUTO · SHORTS · REELS · TIKTOK</text>
      <path d="M-100 300 L 300 217 L 900 217 L 1300 300 Z" fill={`url(#${id}p)`} />
      {[...Array(8)].map((_, i) => <path key={i} d={`M${300 + i * 75} 217 L ${-100 + i * 175} 300 L ${-12 + i * 175} 300 L ${375 + i * 75} 217Z`} fill="#ffffff" opacity={i % 2 ? 0.05 : 0} />)}
      <path d="M600 217 L600 300" stroke="#fff" strokeWidth="2" opacity="0.8" />
      <ellipse cx="600" cy="262" rx="120" ry="26" stroke="#fff" strokeWidth="2" fill="none" opacity="0.8" />
    </>
  );
}

/** Ilustración del canal. `compact` recorta a una franja (tarjetas). */
export function ChannelArt({ profile, className }: { profile: string; className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg className={`channel-art ${className ?? ""}`} viewBox="0 0 1200 300" preserveAspectRatio="xMidYMid slice" aria-hidden>
      {profile === "gta6" ? <Vice id={id} /> : profile === "kids" ? <Kids id={id} /> : profile === "deportes" ? <Stadium id={id} /> : <Gotham id={id} />}
    </svg>
  );
}
