# ADR 0002 — Proveedores audiovisuales mediante interfaces y adaptadores

**Estado**: aceptado

## Decisión
Nueve interfaces de capacidad con contrato común y modelo de datos interno `MediaAsset`.
Los agentes solo hablan con `ProviderGateway`; nunca importan adaptadores. Un registro
central gestiona activación, credenciales cifradas, principal/alternativos, costes y salud.
Una batería de pruebas de contrato parametrizada valida cada adaptador.

## Consecuencias
Sustituir un proveedor = añadir adaptador + credenciales + test de contrato + seleccionarlo.
Una prueba de arquitectura impide imports directos de adaptadores desde agentes/orquestador.
