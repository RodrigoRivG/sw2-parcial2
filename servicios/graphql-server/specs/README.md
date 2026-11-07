# Specs — `graphql-server`

Un archivo por funcionalidad, cada uno con tres partes: **Spec** (qué hace), **Plan** (cómo se construye) y **Tareas** (en qué orden se implementa).

- Constitución de referencia: `graphql-server` v1.0.0 (2026-11-06). Si un archivo la contradice, prevalece la constitución.
- Documento de requisitos: `SW2_Parcial_2.pdf` (RF-27, proceso 7, Módulos 6 y 9).
- Criterio: lo más simple que cumpla el documento de requisitos y la constitución. Es un proyecto de examen, no un sistema en producción.

Los cuatro microservicios, el API Gateway y el realm de Keycloak ya están implementados. Antes de escribir un cliente se revisa el contrato real del servicio consultado (su `specs/` y su OpenAPI), no se supone.

## Índice y orden de implementación

| Orden | ID | Archivo | Funcionalidad | Prioridad | CU | RF |
|---|---|---|---|---|---|---|
| 1 | GQL-001 | [spec-consultas.md](spec-consultas.md) | Base del servidor y consultas consolidadas de gestión, inventario, operaciones e IA para React | Media (soporte de CU-05 y CU-24; baja para CU-14 y CU-15) | CU-05, CU-14, CU-15, CU-24 | RF-27 |

Requiere la ruta `/api/graphql` del gateway (`servicios/api-gateway/specs/spec-ruta-graphql.md`).

## Historial de decisiones (2026-11-06)

- Constitución y spec antes que el código, como en los demás servicios.
- Solo consultas: lo que crea datos o lanza procesos de IA va por REST al servicio dueño.
- React llega a través del gateway, en `/api/graphql`.
- Cuenta de servicio `graphql-server` hacia los microservicios (ya definida en el realm), con permisos por campo que nunca superan los del usuario.
