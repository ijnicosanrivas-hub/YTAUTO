import { useEffect, useState } from "react";
import { getToken } from "../api";
import { figureImage } from "../channels";
import { avatarFor } from "../minifig/avatars";
import type { PersonaRef } from "../types";
import { Portrait } from "./Portrait";

/** Cara de un personaje: su imagen (recortada a la cabeza) si el perfil la tiene; si no, su icono sobre su color. */
export function Face({ theme, agent, persona, size = 44, image = true, ring }: {
  theme: string; agent: string; persona: PersonaRef | null | undefined; size?: number; image?: boolean; ring?: string;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [theme, agent]); // otra imagen: se vuelve a intentar
  const color = persona?.color ?? "#64748b";
  const style: React.CSSProperties = { width: size, height: size, borderColor: ring ?? color, ["--face" as string]: color };
  const showImg = image && !failed;
  const spec = avatarFor(theme, agent);
  return (
    <span className="face" style={style} title={persona?.character}>
      {showImg ? (
        <img src={figureImage(theme, agent, getToken() || null)} alt={persona?.character ?? agent} onError={() => setFailed(true)} draggable={false} />
      ) : spec ? (
        <Portrait spec={spec} bg={color} />
      ) : (
        <span className="face-glyph" style={{ fontSize: size * 0.5 }} aria-hidden>{persona?.glyph ?? "🎬"}</span>
      )}
    </span>
  );
}
