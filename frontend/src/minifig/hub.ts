/**
 * Disposición del hub de la Batcueva: cada agente trabaja en una instalación del juego y todos reportan a Batman.
 * Funciones puras (sin Three.js) para poder comprobarlas.
 */
import { describeEvent } from "../format";
import type { YtEvent } from "../types";

export interface Station {
  name: string; // instalación de la Batcueva
  blurb: string; // qué hace esa instalación en la fábrica
  x: number;
  z: number;
}

/** Instalaciones del hub (inspiradas en las del videojuego: Batcomputer, mesa de trabajo, bóveda de trajes…). */
export const HUB: Record<string, Station> = {
  chief: { name: "Batcomputer", blurb: "Centro de mando: coordina las 20 fases, controla el presupuesto y redacta el informe.", x: 0, z: 0 },
  director: { name: "Tablero de desafíos", blurb: "Planifica el concepto, el estilo y la estructura de retención del vídeo.", x: -6.2, z: -8.2 },
  scriptwriter: { name: "Muro de casos", blurb: "Conecta ideas con hilo rojo: escribe el gancho y la narración.", x: 6.2, z: -8.2 },
  publisher: { name: "Garaje del Batmóvil", blurb: "Prepara las exportaciones y entrega el paquete, solo con tu autorización.", x: -11.5, z: -3.5 },
  voice: { name: "Zona de entrenamiento", blurb: "Entrena la locución: ritmo, pausas y subtítulos alineados.", x: 11.5, z: -3.5 },
  resources: { name: "Bóveda de trajes", blurb: "Busca y prepara las imágenes y clips, siempre con licencia.", x: -10.5, z: 4.5 },
  sound: { name: "Tienda Bat-Mite", blurb: "Música, efectos y mezcla: pone el sonido a cada escena.", x: 10.5, z: 4.5 },
  editor: { name: "Mesa de trabajo", blurb: "Monta las escenas, la cámara y las transiciones, y renderiza.", x: -5.2, z: 9.2 },
  reviewer: { name: "Mesa de pruebas", blurb: "Revisión independiente: puntúa el vídeo y pide correcciones.", x: 5.2, z: 9.2 },
};

/** Escala con la que se dibuja cada personaje con su instalación en el hub. */
export const HUB_SCALE = 1.5;

/** Giro (sobre Y) con el que un personaje mira a Batman; Batman mira a la cámara. Su «delante» local es +z. */
export function facingYaw(name: string): number {
  const s = HUB[name];
  if (!s || name === "chief") return 0;
  return Math.atan2(-s.x, -s.z);
}

/** Convierte un desplazamiento local del personaje (x derecha, z delante) a coordenadas del mundo. */
export function localToWorld(name: string, lx: number, lz: number, yaw: number = facingYaw(name)): [number, number] {
  const s = HUB[name];
  const c = Math.cos(yaw), sn = Math.sin(yaw);
  return [s.x + lx * c + lz * sn, s.z - lx * sn + lz * c];
}

export interface CameraShot { position: [number, number, number]; target: [number, number, number] }

export const OVERVIEW: CameraShot = { position: [0, 8.2, 20.5], target: [0, 1.3, -2.5] };

/**
 * Plano de cámara al pulsar un agente: sobre el hombro, desde el lado de Batman, mirando al pecho del personaje.
 * (Al trabajar, el personaje se gira hacia su instalación y la cámara lo ve de espaldas, trabajando.)
 */
export function focusShot(name: string, feetY: number): CameraShot {
  const s = HUB[name];
  if (!s) return OVERVIEW;
  const target: [number, number, number] = [s.x, feetY + 1.5 * HUB_SCALE, s.z];
  const [px, pz] = localToWorld(name, 3.2, 6.2);
  return { position: [px, feetY + 2.3 * HUB_SCALE, pz], target };
}

export interface Action { at: string; text: string; type: string }

/**
 * Últimas acciones REALES de un agente: eventos suyos (o de una fase que le corresponde), más recientes primero.
 * Se omiten los avances intermedios salvo el último, para que la lista sea legible.
 */
export function recentActions(events: YtEvent[], agent: string, phaseAgent: Record<string, string | null>, limit = 8): Action[] {
  const mine = events.filter((e) => e.agent === agent || (!e.agent && e.phase != null && phaseAgent[e.phase] === agent));
  const ordered = [...mine].sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
  const out: Action[] = [];
  let progressSeen = false;
  for (const e of ordered) {
    if (e.type === "agent.progress") {
      if (progressSeen) continue;
      progressSeen = true;
    }
    out.push({ at: e.at, type: e.type, text: describeEvent(e.type, e.data) });
    if (out.length >= limit) break;
  }
  return out;
}

/** Nombre y descripción de cada puesto según el perfil del canal (la posición es la misma en todos). */
const PROFILE_STATIONS: Record<string, Record<string, [string, string]>> = {
  gta6: {
    chief: ["Ático de Ocean Drive", "Centro de mando: coordina las 20 fases y el presupuesto, y redacta el informe."],
    director: ["Mesa del plan", "Planifica el golpe: concepto, estilo y estructura de retención."],
    scriptwriter: ["Furgoneta de la radio pirata", "Escribe el gancho y la narración con teorías imposibles de ignorar."],
    publisher: ["Estudio de streaming", "Prepara títulos, hashtags y exportaciones; solo publica con tu permiso."],
    voice: ["Cabina de Only Raw", "Graba la locución con ritmo y pausas."],
    resources: ["Almacén del puerto", "Consigue imágenes y clips, siempre limpios y con licencia."],
    sound: ["Estudio de grabación", "Música, efectos y mezcla con la voz por delante."],
    editor: ["Sala de montaje", "Monta el vídeo vertical, la cámara y las transiciones, y renderiza."],
    reviewer: ["Muelle de los Cayos", "Revisión independiente: puntúa y pide correcciones."],
  },
  kids: {
    chief: ["Casa de juegos", "Organiza el juego: coordina las 20 fases y el informe final."],
    director: ["Rincón de los descubrimientos", "Imagina el concepto y la historia paso a paso."],
    scriptwriter: ["Rincón del cuento", "Escribe frases cortas, claras y divertidas."],
    publisher: ["Buzón de las sorpresas", "Prepara títulos seguros para familias; publica solo con tu permiso."],
    voice: ["Escenario de canciones", "Pone la voz con ritmo y alegría."],
    resources: ["Caja de los tesoros", "Busca dibujos e imágenes adecuadas y con licencia."],
    sound: ["Orquesta de juguete", "Canciones y efectos suaves que no tapan la voz."],
    editor: ["Mesa de colores", "Monta escenas claras y fáciles de seguir."],
    reviewer: ["Consulta de juguetes", "Chequeo de calidad y seguridad para peques."],
  },
  deportes: {
    chief: ["Palco presidencial", "Dirige el club: coordina las 20 fases, el presupuesto y el informe."],
    director: ["Banquillo", "Diseña la jugada: concepto, estilo y ritmo."],
    scriptwriter: ["Cabina de prensa", "Narra la jugada con datos y emoción."],
    publisher: ["Sala de redes", "Prepara publicaciones; solo publica con tu permiso."],
    voice: ["Megafonía", "Locución con energía de gran final."],
    resources: ["Grada de ojeadores", "Encuentra imágenes con derechos para cada jugada."],
    sound: ["Fondo de animación", "Música y ambiente de grada sin tapar al narrador."],
    editor: ["Unidad móvil de TV", "Elige las repeticiones y monta con ritmo de directo."],
    reviewer: ["Sala VAR", "Revisa cada jugada antes de dar el gol por bueno."],
  },
};

/** Puesto de un agente en el perfil indicado (por defecto, las instalaciones de la Baticueva). */
export function stationFor(profile: string, agent: string): Station | undefined {
  const base = HUB[agent];
  const named = PROFILE_STATIONS[profile]?.[agent];
  return base && named ? { ...base, name: named[0], blurb: named[1] } : base;
}

/** ¿Tiene el perfil su propia sala inmersiva? */
export const PROFILE_WORLDS = ["gotham", "gta6", "kids", "deportes"] as const;
export function hasWorld(profile: string): boolean {
  return (PROFILE_WORLDS as readonly string[]).includes(profile);
}
