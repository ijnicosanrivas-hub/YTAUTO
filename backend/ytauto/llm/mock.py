"""Motores LLM sin Claude, para pruebas y producción de prueba sin consumo.

- `ScriptedLLM`: respuestas programadas por agente (tests unitarios, simulación de errores).
- `LocalDraftLLM`: genera borradores deterministas a partir del contexto. NO sustituye a
  Claude en calidad creativa: existe para validar el sistema extremo a extremo sin gastar
  consumo de la suscripción.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Callable

from .base import LLMProvider, LLMRequest, LLMResponse, LLMUsage

Handler = Callable[[LLMRequest], dict[str, Any] | Exception]


class ScriptedLLM(LLMProvider):
    name = "scripted"

    def __init__(self, handlers: dict[str, Handler | list[dict | Exception]] | None = None,
                 fallback: LLMProvider | None = None):
        self.handlers = handlers or {}
        self.fallback = fallback
        self.calls: list[LLMRequest] = []
        self._counters: dict[str, int] = defaultdict(int)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        h = self.handlers.get(request.agent)
        if h is None:
            if self.fallback:
                return self.fallback.complete(request)
            raise KeyError(f"Sin respuesta programada para {request.agent}")
        if isinstance(h, list):
            i = min(self._counters[request.agent], len(h) - 1)
            self._counters[request.agent] += 1
            out = h[i]
        else:
            out = h(request)
        if isinstance(out, Exception):
            raise out
        return LLMResponse(data=out, usage=LLMUsage(duration_s=0.01, model_served=f"mock-{request.model}"))


def _clip_words(text: str, max_words: int) -> str:
    words = text.split()
    return " ".join(words[:max(1, max_words)]).rstrip(",;:") + ("." if not text.endswith((".", "?", "!")) else "")


class LocalDraftLLM(LLMProvider):
    name = "local_draft"

    def complete(self, request: LLMRequest) -> LLMResponse:
        fn = getattr(self, f"_{request.agent}", None)
        if fn is None:
            raise KeyError(f"LocalDraftLLM no soporta el agente {request.agent}")
        return LLMResponse(data=fn(request.context), usage=LLMUsage(duration_s=0.0, model_served="local-draft"))

    # ------------------------------------------------------------------ director
    def _director(self, c: dict) -> dict:
        topic = c["user_request"]["topic"]
        target = c["target_duration_s"]
        hook_max = c["hook_max_s"]
        scenes, idx = [], 0
        motions = ["slow_zoom_in", "pan_left", "zoom_out", "pan_right", "pan_up", "ken_burns"]
        transitions = ["cut", "fade", "slideleft", "cut", "zoomin", "wipeleft", "cut", "slideup"]
        for slot in c["section_slots"]:
            dur = slot["duration_s"]
            if slot["section"] == "hook":
                parts = [min(dur, hook_max)]
            else:
                n = max(1, round(dur / 5.0))
                parts = [dur / n] * n
            for d in parts:
                scenes.append({
                    "index": idx, "section": slot["section"], "duration_s": round(d, 2),
                    "purpose": f"{slot['section']} sobre {topic}",
                    "visual_direction": f"Plano vertical relacionado con {topic}, parte {idx + 1}",
                    "camera_motion": motions[idx % len(motions)],
                    "transition": transitions[idx % len(transitions)],
                    "on_screen_text": topic.upper()[:28] if idx == 0 else None,
                    "sfx": ["impact"] if slot["section"] == "climax" else [],
                })
                idx += 1
        return {
            "concept": f"Vídeo corto sobre {topic}", "tone": "intrigante y dinámico",
            "visual_style": c["user_request"].get("visual_style") or "cinemático, alto contraste",
            "palette": ["#0B0F1A", "#FFD400", "#FFFFFF"], "pacing": "rápido",
            "target_duration_s": target, "music_direction": c["user_request"].get("music") or "electrónica tensa",
            "scenes": scenes, "resource_needs": ["imágenes verticales", "música", "efectos"],
        }

    # ------------------------------------------------------------------ guionista
    _HOOKS = ["¿Sabías que {t} esconde algo que casi nadie conoce?", "Esto sobre {t} te va a sorprender.",
              "Nadie te contó esto.", "Mira esto."]
    _CLOSES = ["Ahora ya conoces la parte de {t} que casi todos ignoran. Síguenos para descubrir más.",
               "Ahora ya conoces el secreto. Síguenos para más.", "Ahora ya lo sabes.", "Síguenos."]
    _POOL = [
        "Para entenderlo hay que mirar de dónde viene {t} y por qué importa tanto hoy.",
        "El primer detalle sorprende, porque todo empezó mucho antes de lo que imaginas.",
        "Después llegó un cambio que transformó por completo esta historia.",
        "Los expertos tardaron años en descubrir la pieza que faltaba en el puzle.",
        "Cada nuevo dato encajaba como un rompecabezas inesperado y fascinante.",
        "Y entonces apareció la prueba que nadie esperaba encontrar.",
        "Esa pista cambió para siempre la forma de ver todo lo anterior.",
        "Lo más increíble es que sigue ocurriendo ahora mismo, delante de nosotros.",
        "Hay quien piensa que es casualidad, pero los números dicen lo contrario.",
        "Si lo comparas con cualquier otro caso, la diferencia resulta enorme.",
        "Detrás de cada respuesta aparecía una pregunta todavía más interesante.",
        "Imagina lo que significa esto a escala de todo el planeta.",
        "Por eso los investigadores siguen estudiándolo con tanta atención.",
        "Y lo mejor es que todavía quedan secretos por descubrir.",
        "Parece sencillo, pero no lo es.",
        "Y aquí viene lo interesante.",
        "Los datos no mienten.",
        "Nadie lo vio venir.",
        "Todo cambió en un instante.",
        "La respuesta está más cerca de lo que crees.",
        "Y eso no es todo.",
        "Fíjate bien en este detalle.",
        "Es más común de lo que parece.",
        "Y no es una exageración.",
        "Suena raro, ¿verdad?",
        "Pero hay más.",
        "Vamos por partes.",
        "Aquí está la clave.",
        "Eso lo explica todo.",
        "La ciencia lo confirma.",
        "Y pasa cada día.",
        "Nadie habla de esto.",
        "Ojo a este dato.",
        "Esto sí que sorprende.",
        "Hablemos de {t}.",
        "Un detalle casi invisible.",
        "Y el resultado es asombroso.",
        "Así funciona en realidad.",
        "Increíble, ¿no?",
        "Atento ahora.",
        "Fascinante.",
        "Y funciona.",
        "Piénsalo.",
    ]
    _EXTRA = ["Y hay un detalle más que lo cambia todo.", "Piensa en ello la próxima vez que lo veas.",
              "Nadie lo había explicado así hasta ahora.", "Y eso lo cambia todo."]

    @staticmethod
    def _words(text: str) -> int:
        return len(text.split())

    def _pack(self, pool: list[str], used: set[str], budget: int, topic: str) -> list[str]:
        """Elige frases COMPLETAS no usadas que quepan en el presupuesto (nunca trunca)."""
        chosen: list[str] = []
        remaining = budget
        while remaining >= 1:
            fits = [p.format(t=topic) for p in pool if p not in used and self._words(p.format(t=topic)) <= remaining]
            if not fits:
                break
            best = max(fits, key=self._words)
            chosen.append(best)
            used.add(next(p for p in pool if p.format(t=topic) == best))
            remaining -= self._words(best)
        return chosen

    def _scriptwriter(self, c: dict) -> dict:
        brief = c["creative_brief"]
        topic = c["topic"]
        maxw = {int(k): v for k, v in c["max_words_per_scene"].items()}
        scenes: list[dict] = []
        used: set[str] = set()
        n = len(brief["scenes"])
        rewrite = set(c.get("rewrite_only_scenes") or [])
        for i, sc in enumerate(brief["scenes"]):
            budget = max(2, int(maxw[sc["index"]]))
            if i in (0, n - 1):
                options = self._HOOKS if i == 0 else self._CLOSES
                text = next((o.format(t=topic) for o in options if self._words(o.format(t=topic)) <= budget),
                            options[-1].format(t=topic))
            else:
                sentences = self._pack(self._POOL, used, budget, topic)
                if sc["index"] in rewrite:
                    sentences += self._pack(self._EXTRA, used, budget - self._words(" ".join(sentences)), topic)
                text = " ".join(sentences) or f"Dato {i}: {topic}."
            scenes.append({
                "index": sc["index"], "section": sc["section"], "duration_s": sc["duration_s"],
                "narration": text, "dialogue": [], "visual_notes": sc["visual_direction"],
                "sfx": sc.get("sfx", []), "music_cue": None, "subtitle_lines": [],
            })
        return {
            "internal_title": f"{topic[:40]} — borrador", "topic": topic,
            "narrative_goal": f"Despertar curiosidad sobre {topic}",
            "hook": scenes[0]["narration"], "closing": scenes[-1]["narration"],
            "call_to_action": None, "music": brief.get("music_direction", ""), "scenes": scenes,
        }

    # ------------------------------------------------------------------ recursos
    def _resources(self, c: dict) -> dict:
        prompts = []
        for sc in c["scenes"]:
            words = re.findall(r"\w+", sc["visual_direction"].lower())[:4]
            prompts.append({
                "scene_index": sc["index"], "kind": "image",
                "prompt": f"Vertical 9:16 cinematic shot, {sc['visual_direction']}, {c['visual_style']}, dramatic lighting",
                "search_query": " ".join(words) + f" {sc['index']}",
                "style_tags": [c["visual_style"]],
            })
        return {"style_guide": f"{c['visual_style']}; paleta {', '.join(c.get('palette', []))}", "prompts": prompts}

    def _voice(self, c: dict) -> dict:
        return {"scenes": c["scenes"]}

    def _reviewer(self, c: dict) -> dict:
        return {"scores": {"hook": 8, "pacing": 8, "coherence": 8, "spelling": 9, "legibility": 9},
                "issues": [], "summary": "Borrador local: revisión editorial automática sin Claude."}

    def _publisher(self, c: dict) -> dict:
        topic = c["topic"]
        tags = ["#" + re.sub(r"\W", "", w) for w in topic.split() if len(w) > 3][:3] + ["#shorts", "#curiosidades"]
        items = []
        for p in c["platforms"]:
            lim = c["limits"][p]
            items.append({
                "platform": p, "title": topic[: lim["title_max_chars"]],
                "description": c["hook"][: lim["description_max_chars"] // 2],
                "hashtags": tags[: lim["hashtags_max"]],
            })
        return {"items": items}
