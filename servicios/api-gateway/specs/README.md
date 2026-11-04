# Specs — `api-gateway`

Un archivo por funcionalidad, cada uno con tres partes: **Spec** (qué hace), **Plan** (cómo se construye) y **Tareas** (en qué orden se implementa).

- Constitución de referencia: `api-gateway` v1.0.0 (2026-11-04). Si un archivo la contradice, prevalece la constitución.
- Documento de requisitos: `SW2_Parcial_2.pdf` (Módulo 9, RNF-01 a RNF-22).
- Criterio: lo más simple que cumpla el documento de requisitos y la constitución. Es un proyecto de examen, no un sistema en producción.

## Índice y orden de implementación

| Orden | ID | Archivo | Funcionalidad | Prioridad |
|---|---|---|---|---|
| 1 | GW-001 | [spec-enrutamiento.md](spec-enrutamiento.md) | Enrutamiento, validación del token, correlación, CORS y errores | Alta (bloquea la prueba de punta a punta de la Saga) |

## Mapa de rutas

| Prefijo | Destino |
|---|---|
| `/api/gestion/**` | `servicio-gestion` |
| `/api/inventario/**` | `servicio-inventario` |
| `/api/operaciones/**` | `servicio-operaciones` |
| `/api/ia/**` | `servicio-ia` |

Del propio gateway, sin token: `/salud`, `/salud/liveness` y `/salud/readiness`.
