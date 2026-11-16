# ADR 0001 — Claude Code CLI como motor de inteligencia

**Estado**: aceptado

## Contexto
Una única licencia Claude Pro, sin acceso a la API de Anthropic. Se necesitan 9 agentes.

## Decisión
Los agentes invocan el binario oficial `claude` en modo `-p` (no interactivo) con
`--agent`, `--model`, `--output-format json` y `--json-schema`. La autenticación es la
sesión de Claude Code del usuario. Una cola central limita la concurrencia (1 por defecto).

## Consecuencias
- Cumple los términos: sin multiplicar cuentas ni extraer credenciales.
- El consumo comparte los límites de la suscripción con claude.ai; hay que pausar ante límites.
- `LLMProvider` es una interfaz: un futuro adaptador de API no afecta a los agentes.
