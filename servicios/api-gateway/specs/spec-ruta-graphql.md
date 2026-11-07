# Ruta al servidor GraphQL — `api-gateway`

| Campo | Valor |
|---|---|
| Servicio | `api-gateway` |
| Archivo | `specs/spec-ruta-graphql.md` |
| Estado | Spec en borrador (2026-11-06) · Plan y tareas en borrador |
| Constitución | v1.1.0 |
| Trazabilidad | Módulo 9 · proceso 7 · RF-27 · RNF-01, RNF-05, RNF-08, RNF-22 |
| Depende de | `spec-enrutamiento.md` (implementada). Para la prueba de punta a punta, `graphql-server/specs/spec-consultas.md`. |

Contenido:

1. [Spec](#1-spec): qué debe hacer el gateway.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

React consulta el servidor GraphQL con Apollo Client (RF-27, proceso 7). `spec-enrutamiento.md` dejó a `graphql-server` fuera del gateway (1.8) porque solo se lo veía como cliente. El 2026-11-06 se decidió que React también llegue a GraphQL a través del gateway, para usar una sola URL y que el gateway aplique a GraphQL la misma validación del token, CORS y correlación que a los microservicios (constitución v1.1.0).

## 1.1 Escenarios de usuario y pruebas

### Historia 1 — Llegar al servidor GraphQL por el gateway (Prioridad: P1)

Como microfrontend React, quiero enviar mis consultas GraphQL a la misma URL base que el resto del backend.

**Prueba independiente:** con el servidor GraphQL simulado (WireMock), se envía una consulta y se verifica que llega intacta.

**Escenarios de aceptación:**

1. **Dado** un token válido, **cuando** se envía `POST /api/graphql` con `Content-Type: application/json` y una consulta, **entonces** `graphql-server` recibe exactamente esa ruta, el cuerpo, el header `Authorization` y el `X-Correlation-Id`, y el cliente recibe su respuesta sin cambios (código, headers y cuerpo).
2. **Dado** que `graphql-server` responde `200` con una lista `errors` (errores de campo de GraphQL), **entonces** el cliente recibe ese mismo `200` y ese cuerpo.
3. **Dado** una solicitud sin token o con un token inválido, **entonces** `401 NO_AUTENTICADO` y `graphql-server` no recibe nada.
4. **Dado** una verificación previa de CORS (`OPTIONS /api/graphql`) desde un origen permitido, **entonces** `200` con los headers de CORS, sin token.
5. **Dado** `POST /api/graphqlx` o `POST /api/graphql/otra`, **entonces** `404 RUTA_NO_ENCONTRADA`.
6. **Dado** que `graphql-server` no está levantado, **entonces** `503 SERVICIO_NO_DISPONIBLE` y las demás rutas siguen respondiendo.
7. **Dado** cualquier solicitud a `/api/graphql`, **entonces** el log de acceso informa `servicioDestino = graphql-server`.

### Casos borde

- **Consulta GraphQL lenta:** se aplica el tiempo límite general (`GATEWAY_TIEMPO_LIMITE`, 10 s), sin un tiempo propio para esta ruta. No debería alcanzarse: `graphql-server` tiene un plazo total de 4,5 s por consulta y, al vencer, responde con los datos que alcanzó a obtener (`spec-consultas.md` D-GQL-06). Un `504 TIEMPO_AGOTADO` en esta ruta indica una falla del propio `graphql-server`.
- **`GET /api/graphql`** (página de Apollo Sandbox o una consulta por GET): se reenvía igual que un `POST`; exige token como toda ruta `/api/**`, así que la página de Sandbox no abre a través del gateway. Sandbox se usa en local contra el puerto 4000 (`spec-consultas.md` 2.5, CORS de desarrollo).
- **Headers de CORS de `graphql-server`:** no los emite para los orígenes de React (`spec-consultas.md` D-GQL-07); el CORS de esta ruta es el del gateway.

## 1.2 Requisitos

- **RF-GW-10:** enrutar `/api/graphql` (ruta exacta) a `graphql-server` (`GRAPHQL_URL`), sin reescribir la ruta, con las mismas reglas de RF-GW-02 a RF-GW-09.

## 1.3 Criterios de éxito

- **CE-RGQ-01:** los escenarios de la historia 1 pasan como tests de integración automatizados.
- **CE-RGQ-02:** la cobertura de líneas sigue ≥ 80 %.
- **CE-RGQ-03:** la prueba de punta a punta de `graphql-server` (CE-GQL-03) pasa a través del gateway.

## 1.4 Supuestos

- `graphql-server` expone su endpoint en `/api/graphql` (`spec-consultas.md` RQ-GQL-01), así que no hace falta reescribir la ruta.
- `graphql-server` valida el token completo (incluida la audiencia), como los microservicios: el gateway sigue sin validar `aud` ni roles.

## 1.5 Fuera de alcance

- Cambios en la seguridad, el CORS o los errores del gateway: `/api/graphql` ya queda cubierta por las reglas de `/api/**`.
- Exponer `/salud` de `graphql-server` a través del gateway.

---

# 2. Plan

- **`application.yml`:** una ruta más:

  ```yaml
  - id: graphql-server
    uri: ${GRAPHQL_URL}
    predicates:
      - Path=/api/graphql
    metadata:
      servicio: graphql-server
  ```

  Si `GRAPHQL_URL` falta, la aplicación no arranca, como con las otras cuatro URL (RNF-03).
- **Java:** sin cambios. `ConfiguracionSeguridad` ya exige token en `/api/**` y permite `OPTIONS /api/**`.
- **`docker-compose.yml`:** `GRAPHQL_URL: http://graphql-server:4000` en el servicio `api-gateway`.
- **`README.md`:** la fila de variables de `api-gateway` suma `GRAPHQL_URL`.
- **`specs/README.md`** del gateway: índice y mapa de rutas.
- **Tests:** `PruebaIntegracionBase.propiedades(registro)` apunta `GRAPHQL_URL` a WireMock, junto con las otras cuatro URL. Va ahí y no en una clase de test: la URL es obligatoria, y una clase IT que no la definiera dejaría al gateway sin arrancar. `EnrutamientoIT` agrega los escenarios 1, 2, 5 y 7; `SeguridadIT`, el 3; `CorsIT`, el 4; `ResilienciaIT`, el 6.

---

# 3. Tareas

- [ ] **T01** — Agregar la ruta y `GRAPHQL_URL` a `application.yml` y a `PruebaIntegracionBase.propiedades(registro)`. *Hecho cuando:* compila y los tests existentes siguen en verde.
- [ ] **T02** — Escribir los escenarios de la historia 1 en los tests de 2. *Hecho cuando:* pasan.
- [ ] **T03** — Actualizar `docker-compose.yml`, `README.md` y `specs/README.md`. *Hecho cuando:* `docker compose --profile gateway --profile graphql up -d` arranca los dos y `curl -X POST localhost:8080/api/graphql` sin token responde `401 NO_AUTENTICADO`.
- [ ] **T04** — Verificación final: `mvn -B verify` en verde con cobertura ≥ 80 %. La prueba de punta a punta (CE-RGQ-03) se marca con T14 de `graphql-server/specs/spec-consultas.md`.
