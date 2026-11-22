import type { AvatarSpec } from "../minifig/avatars";

/** Retrato plano (SVG) de un personaje 3D: la «cara» del agente cuando el perfil no tiene imagen propia. */
export function Portrait({ spec, bg }: { spec: AvatarSpec; bg: string }) {
  const s = spec;
  const animal = s.head !== "human" && s.head !== "baby";
  const r = s.head === "baby" ? 26 : 23;
  const cy = 47;
  const hair = s.hair?.color ?? "#222";
  const eyeY = cy + (animal ? -1 : 1);
  const eyeX = s.head === "baby" ? 10 : 9;
  const eyeR = s.head === "human" ? 4 : 5.2;
  const id = `g${Math.abs([...JSON.stringify(s)].reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 7))}`;
  return (
    <svg viewBox="0 0 100 100" width="100%" height="100%" aria-hidden>
      <defs>
        <radialGradient id={id} cx="50%" cy="35%" r="70%">
          <stop offset="0%" stopColor={bg} stopOpacity="0.95" />
          <stop offset="100%" stopColor="#0b0d12" />
        </radialGradient>
      </defs>
      <rect width="100" height="100" fill={`url(#${id})`} />
      {/* hombros */}
      <path d="M14 104 Q16 76 50 74 Q84 76 86 104 Z" fill={s.top} />
      {s.topStyle === "suit" && <path d="M44 75 L50 92 L56 75 Z" fill="#f8fafc" />}
      {s.chain && <path d="M38 77 Q50 90 62 77" stroke="#e8b931" strokeWidth="2.6" fill="none" />}
      <rect x="44" y="64" width="12" height="12" fill={s.skin} />
      {/* pelo de detrás */}
      {s.hair?.style === "long" && <rect x={50 - r - 3} y={cy - 6} width={(r + 3) * 2} height="34" rx="10" fill={hair} />}
      {s.hair?.style === "ponytail" && <ellipse cx={50 + r - 2} cy={cy + 14} rx="6" ry="14" fill={hair} />}
      {/* orejas de animal */}
      {s.head === "dog" && <><path d={`M${50 - r + 2} ${cy - 12} L${50 - r - 4} ${cy - 34} L${50 - 8} ${cy - r + 2} Z`} fill={s.ears} /><path d={`M${50 + r - 2} ${cy - 12} L${50 + r + 4} ${cy - 34} L${50 + 8} ${cy - r + 2} Z`} fill={s.ears} /></>}
      {s.head === "fox" && <><path d={`M${50 - r + 3} ${cy - 10} L${50 - r} ${cy - 40} L${50 - 6} ${cy - r + 1} Z`} fill={s.ears} /><path d={`M${50 + r - 3} ${cy - 10} L${50 + r} ${cy - 40} L${50 + 6} ${cy - r + 1} Z`} fill={s.ears} /></>}
      {s.head === "pig" && <><path d={`M${50 - 15} ${cy - r + 4} l-6 -12 l12 6 Z`} fill={s.ears} /><path d={`M${50 + 15} ${cy - r + 4} l6 -12 l-12 6 Z`} fill={s.ears} /></>}
      {s.head === "shark" && <path d={`M44 ${cy - r - 4} L52 ${cy - r - 22} L58 ${cy - r - 2} Z`} fill={s.skin} />}
      {/* cabeza */}
      {s.head === "shark" ? <ellipse cx="50" cy={cy} rx={r} ry={r * 1.15} fill={s.skin} /> : <circle cx="50" cy={cy} r={r} fill={s.skin} />}
      {s.head === "shark" && <ellipse cx="50" cy={cy + 12} rx={r * 0.8} ry="11" fill={s.snout} />}
      {/* pelo de arriba */}
      {s.hair && !["bald", "tuft", "curly"].includes(s.hair.style) && (
        <path d={`M${50 - r - 1} ${cy - 2} Q${50 - r} ${cy - r - 9} 50 ${cy - r - 6} Q${50 + r} ${cy - r - 9} ${50 + r + 1} ${cy - 2} Q${50 + r - 4} ${cy - 15} 50 ${cy - 16} Q${50 - r + 4} ${cy - 15} ${50 - r - 1} ${cy - 2} Z`} fill={hair} />
      )}
      {s.hair?.style === "bun" && <circle cx="50" cy={cy - r - 7} r="8" fill={hair} />}
      {s.hair?.style === "tuft" && <path d={`M47 ${cy - r + 1} Q50 ${cy - r - 12} 55 ${cy - r - 6} Q51 ${cy - r - 3} 53 ${cy - r + 1} Z`} fill={hair} />}
      {s.hair?.style === "curly" && [...Array(7)].map((_, i) => <circle key={i} cx={50 - r + 4 + i * ((2 * r - 8) / 6)} cy={cy - r + 4 - Math.sin((i / 6) * Math.PI) * 8} r="8" fill={hair} />)}
      {s.hair?.style === "dreads" && [...Array(6)].map((_, i) => <rect key={i} x={50 - r - 4 + (i < 3 ? i * 3 : 2 * r - 2 + (i - 3) * 3)} y={cy - 6} width="3" height="24" rx="1.5" fill={hair} />)}
      {/* ojos */}
      {[-1, 1].map((d) => (
        <g key={d}>
          <circle cx={50 + d * eyeX} cy={eyeY} r={eyeR} fill="#fff" />
          <circle cx={50 + d * eyeX + 0.6} cy={eyeY + 0.6} r={eyeR * 0.55} fill="#111" />
          <circle cx={50 + d * eyeX + 1.6} cy={eyeY - 1} r={eyeR * 0.2} fill="#fff" />
        </g>
      ))}
      {/* hocicos y boca */}
      {s.head === "dog" && <><ellipse cx="50" cy={cy + 11} rx="11" ry="7" fill={s.snout} /><ellipse cx="50" cy={cy + 7} rx="4" ry="3" fill="#111" /></>}
      {s.head === "fox" && <><path d={`M38 ${cy + 4} L50 ${cy + 18} L62 ${cy + 4} Z`} fill={s.snout} /><circle cx="50" cy={cy + 15} r="2.6" fill="#111" /></>}
      {s.head === "pig" && <><ellipse cx="50" cy={cy + 10} rx="9" ry="6.5" fill={s.snout} /><circle cx="47" cy={cy + 10} r="1.6" fill="#9d174d" /><circle cx="53" cy={cy + 10} r="1.6" fill="#9d174d" /></>}
      {s.head === "shark" && [...Array(5)].map((_, i) => <path key={i} d={`M${41 + i * 4.5} ${cy + 9} l2.2 4.5 l2.2 -4.5 Z`} fill="#fff" />)}
      {(s.head === "human" || s.head === "baby") && <path d={`M43 ${cy + 10} Q50 ${cy + 16} 57 ${cy + 10}`} stroke="#7f1d1d" strokeWidth="2.2" fill="none" strokeLinecap="round" />}
      {s.beard && <path d={`M${50 - r + 3} ${cy + 3} Q${50 - r + 6} ${cy + r + 2} 50 ${cy + r + 3} Q${50 + r - 6} ${cy + r + 2} ${50 + r - 3} ${cy + 3} Q50 ${cy + 13} ${50 - r + 3} ${cy + 3} Z`} fill={s.beard} opacity="0.92" />}
      {/* gafas */}
      {s.glasses === "sun" && <><rect x={50 - eyeX - 7} y={eyeY - 4} width="14" height="8" rx="2" fill="#111" /><rect x={50 + eyeX - 7} y={eyeY - 4} width="14" height="8" rx="2" fill="#111" /><rect x="46" y={eyeY - 2} width="8" height="1.6" fill="#111" /></>}
      {s.glasses === "round" && [-1, 1].map((d) => <circle key={d} cx={50 + d * eyeX} cy={eyeY} r="6.5" stroke="#111" strokeWidth="1.8" fill="none" />)}
      {s.item === "headphones" && <><path d={`M${50 - r - 2} ${cy} Q50 ${cy - r - 18} ${50 + r + 2} ${cy}`} stroke="#111" strokeWidth="3.5" fill="none" /><rect x={50 - r - 6} y={cy - 6} width="8" height="13" rx="3" fill="#ef4444" /><rect x={50 + r - 2} y={cy - 6} width="8" height="13" rx="3" fill="#ef4444" /></>}
      {/* sombreros */}
      {s.hat?.kind === "cap" && <><path d={`M${50 - r} ${cy - 8} Q50 ${cy - r - 12} ${50 + r} ${cy - 8} Z`} fill={s.hat.color} /><path d={`M${50 - 4} ${cy - 9} Q${50 + 14} ${cy - 13} ${50 + r + 8} ${cy - 6} L${50 - 4} ${cy - 6} Z`} fill={s.hat.color} /></>}
      {s.hat?.kind === "beanie" && <path d={`M${50 - r - 1} ${cy - 4} Q50 ${cy - r - 18} ${50 + r + 1} ${cy - 4} Z`} fill={s.hat.color} />}
      {s.hat?.kind === "police" && <><rect x={50 - r + 1} y={cy - r - 8} width={2 * r - 2} height="14" rx="3" fill={s.hat.color} /><rect x={50 - r} y={cy - r + 4} width={2 * r} height="4" fill="#111" /><circle cx="50" cy={cy - r - 1} r="3" fill="#e8b931" /></>}
      {s.hat?.kind === "cowboy" && <><ellipse cx="50" cy={cy - r + 3} rx={r + 14} ry="5" fill={s.hat.color} /><rect x={50 - r + 6} y={cy - r - 12} width={2 * r - 12} height="16" rx="6" fill={s.hat.color} /></>}
      {s.hat?.kind === "headband" && <rect x={50 - r} y={cy - r + 8} width={2 * r} height="5" fill={s.hat.color} />}
    </svg>
  );
}
