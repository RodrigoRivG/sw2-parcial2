# Specs — `api-gateway`

Un archivo por funcionalidad, cada uno con tres partes: **Spec** (qué hace), **Plan** (cómo se construye) y **Tareas** (en qué orden se implementa).

- Constitución de referencia: `api-gateway` v1.1.0 (2026-11-06). Si un archivo la contradice, prevalece la constitución.
- Documento de requisitos: `SW2_Parcial_2.pdf` (Módulo 9, RNF-01 a RNF-22).
- Criterio: lo más simple que cumpla el documento de requisitos y la constitución. Es un proyecto de examen, no un sistema en producción.

## Índice y orden de implementación

| Orden | ID | Archivo | Funcionalidad | Prioridad |
|---|---|---|---|---|
| 1 | GW-001 | [spec-enrutamiento.md](spec-enrutamiento.md) | Enrutamiento, validación del token, correlación, CORS y errores | Alta (bloquea la prueba de punta a punta de la Saga) |
| 2 | GW-002 | [spec-ruta-graphql.md](spec-ruta-graphql.md) | Ruta `/api/graphql` hacia `graphql-server` | Media (bloquea la prueba de punta a punta de GraphQL) |

## Mapa de rutas

| Prefijo | Destino |
|---|---|
| `/api/gestion/**` | `servicio-gestion` |
| `/api/inventario/**` | `servicio-inventario` |
| `/api/operaciones/**` | `servicio-operaciones` |
| `/api/ia/**` | `servicio-ia` |
| `/api/graphql` (ruta exacta) | `graphql-server` |

Del propio gateway, sin token: `/salud`, `/salud/liveness` y `/salud/readiness`.

## Historial de decisiones

- (2026-11-08) Descarga del JWKS con cliente propio (2 s de conexión, 5 s de respuesta y plazo total de 8 s, configurables) y `AutenticacionNoDisponible` con prioridad sobre las causas de conexión. Así se cierra la limitación conocida de `spec-enrutamiento.md`; la cubren tres pruebas nuevas (JWKS lento, conexión rechazada y nombre no resuelto).
