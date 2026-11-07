# Constitución — API Gateway (`api-gateway`)

> Reglas no negociables del gateway. Prevalecen sobre specs, planes y tareas.
> Si una spec contradice esta constitución, se corrige la spec o se enmienda la constitución; nunca se ignora.
> El gateway no es uno de los cuatro microservicios de negocio: no copia sus secciones **[común]**, pero respeta su contrato (rutas, seguridad, formato de error y correlación) para que los servicios no noten diferencia entre un cliente y otro. La sección «Convenciones» sí se adopta completa.

## 1. Propósito y límites

**Responsable de:**
- Ser el único punto de entrada HTTP del backend para los microfrontends (Angular, React y Vue.js), Flutter, el servidor GraphQL, n8n, `servicio-ia` y `servicio-operaciones` (Módulo 9 del documento de requisitos).
- Enrutar cada solicitud al microservicio dueño según el prefijo de la ruta.
- Validar el JWT de Keycloak (firma, emisor y vigencia) antes de enrutar.
- Recibir o generar el `X-Correlation-Id` y propagarlo al servicio destino y en la respuesta (RNF-22).
- Aplicar la política CORS de los microfrontends, que se publican en un origen distinto al del gateway.
- Responder con el formato de error común cuando la ruta no existe, el token no es válido o el servicio destino no responde.

**No es responsable de:**
- Lógica de negocio, validación de datos ni composición de respuestas de varios servicios → cada microservicio y el servidor GraphQL.
- Autorización por rol ni validación de audiencia (`aud`) → cada microservicio (RNF-02, RN-16).
- Emitir tokens, gestionar usuarios o sesiones → Keycloak. La gestión de usuarios desde Angular (RF-32) usa la API de administración de Keycloak directamente, no pasa por el gateway.
- Mensajería: los comandos de la Saga y los eventos viajan por RabbitMQ, nunca por el gateway.
- Exponer la documentación OpenAPI ni las rutas `/salud` de los microservicios.

**Fuera del alcance:** limitación de tráfico (rate limiting), circuit breaker, caché de respuestas, balanceo entre réplicas y agregación de documentación. El documento de requisitos no los pide.

**Trazabilidad:** Módulo 9 · procesos 2, 3 y 12 · RF-27, RF-28 · RN-16 · RNF-01, RNF-02, RNF-03, RNF-05, RNF-08, RNF-19, RNF-20, RNF-21, RNF-22.

## 2. Stack

- Java 21 (LTS) + Spring Boot 3, con la misma línea de versión que `servicio-gestion` (por la imagen de desarrollo compartida).
- Spring Cloud Gateway en su variante reactiva (WebFlux), de la versión de Spring Cloud compatible con esa línea de Spring Boot.
- Spring Security (OAuth2 Resource Server, reactivo) y Actuator.
- Tests: JUnit 5 + WireMock (servicios destino y JWKS simulados) con tokens firmados en el propio test. No se levanta Keycloak en los tests.
- Despliegue: imagen Docker en Azure Container Apps (sección 1.8.5 del documento de requisitos).
- No se introducen lenguajes, frameworks ni bases de datos nuevas sin una enmienda.

## 3. Arquitectura

- El gateway no tiene dominio ni base de datos: no aplica DDD ni capas. Es configuración más unos pocos componentes transversales.
- Las rutas se declaran en `application.yml`, no en código Java. Agregar un servicio es agregar una ruta y su variable de entorno.
- El código Java se limita a:
  - la configuración de seguridad;
  - el filtro de correlación;
  - el manejador de errores que produce el formato común;
  - el registro de acceso (un log por solicitud).
- El gateway no lee ni modifica el cuerpo de las solicitudes ni de las respuestas.

### Estructura de directorios

```text
api-gateway/
├── src/main/java/com/agrosystem/gateway/
│   ├── AplicacionGateway.java
│   ├── security/
│   │   └── ConfiguracionSeguridad.java
│   └── web/
│       ├── FiltroIdCorrelacion.java
│       ├── RegistroAcceso.java
│       ├── RespuestaError.java
│       └── ManejadorErroresGateway.java
├── src/main/resources/
│   └── application.yml                      # rutas, CORS, tiempos límite
├── src/test/java/com/agrosystem/gateway/
│   └── integration/                         # WireMock (sufijo IT, p. ej. EnrutamientoIT.java)
├── specs/
├── Dockerfile
├── pom.xml
└── Constitucion.md
```

- Los nombres de archivo son de referencia y se fijan en el plan.

## 4. Enrutamiento

| Prefijo | Destino | Variable |
|---|---|---|
| `/api/gestion/**` | `servicio-gestion` | `GESTION_URL` |
| `/api/inventario/**` | `servicio-inventario` | `INVENTARIO_URL` |
| `/api/operaciones/**` | `servicio-operaciones` | `OPERACIONES_URL` |
| `/api/ia/**` | `servicio-ia` | `IA_URL` |
| `/api/graphql` (ruta exacta) | `graphql-server` | `GRAPHQL_URL` |

- La ruta se reenvía sin reescribir: `/api/gestion/v1/parcelas` llega igual a `servicio-gestion`. Cada servicio ya expone su prefijo y versión (`/api/<servicio>/v1/...`); `graphql-server` expone `/api/graphql`, sin versión, porque un esquema GraphQL evoluciona agregando campos.
- Se reenvían sin cambios el método, la query, el cuerpo (incluido `multipart/form-data` para fotografías y audio) y los headers, incluido `Authorization`.
- Una ruta que no coincide con ningún prefijo responde `404 RUTA_NO_ENCONTRADA` sin llamar a ningún servicio.
- Cada solicitud reenviada tiene un tiempo límite de respuesta, configurable por variable de entorno. Una ruta puede tener uno propio solo si la spec de su servicio admite respuestas más lentas (hoy, la sincronización por lotes de `servicio-operaciones`). Si se agota, el gateway responde `504 TIEMPO_AGOTADO`.
- El gateway no impone un límite de tamaño al cuerpo: lo reenvía en streaming y cada servicio aplica el suyo.
- Si el servicio destino no acepta la conexión, el gateway responde `503 SERVICIO_NO_DISPONIBLE`. Las demás rutas siguen funcionando (RNF-08).
- Las respuestas del servicio destino, incluidos sus errores 4xx y 5xx, se devuelven tal cual; el gateway no las reescribe.
- El gateway no reintenta solicitudes: un reintento de un `POST` podría duplicar una operación. La idempotencia es responsabilidad de cada servicio.

## 5. Seguridad

- Toda ruta `/api/**` exige un JWT emitido por Keycloak, salvo las solicitudes `OPTIONS` de CORS.
- El gateway valida firma (JWKS de Keycloak, `KEYCLOAK_JWKS_URI`), emisor (`iss`, `KEYCLOAK_ISSUER`) y vigencia (`exp`). Un token ausente o inválido responde `401 NO_AUTENTICADO` y no llega al servicio.
- El gateway **no** valida `aud` ni roles: cada token se dirige a varios servicios y cada uno verifica su audiencia y sus permisos (RNF-02, RN-16).
- El header `Authorization` se reenvía sin cambios. El gateway no emite, canjea ni modifica tokens.
- Rutas sin token: `/salud`, `/salud/liveness` y `/salud/readiness` del propio gateway.
- CORS: los orígenes permitidos se leen de una variable de entorno (`CORS_ORIGENES_PERMITIDOS`); nunca `*`. Se permiten los headers `Authorization`, `Content-Type` y `X-Correlation-Id`, y se expone `X-Correlation-Id` en la respuesta.
- Secretos y configuración solo por variables de entorno (RNF-03). Comunicación externa por HTTPS/TLS en la nube (RNF-01); el TLS lo termina Azure Container Apps.
- Los logs no contienen tokens ni el header `Authorization`; como dato de usuario solo se registra el `sub`.

## 6. Errores y observabilidad

- Los errores que genera el propio gateway usan el formato común de los microservicios:

```json
{
  "codigo": "SERVICIO_NO_DISPONIBLE",
  "mensaje": "El servicio solicitado no está disponible en este momento.",
  "detalles": [],
  "idCorrelacion": "uuid"
}
```

| Código HTTP | `codigo` | Cuándo |
|---|---|---|
| 401 | `NO_AUTENTICADO` | Token ausente, mal formado, con firma o emisor inválidos o vencido |
| 404 | `RUTA_NO_ENCONTRADA` | La ruta no coincide con ningún prefijo |
| 503 | `SERVICIO_NO_DISPONIBLE` | El servicio destino rechaza la conexión |
| 503 | `AUTENTICACION_NO_DISPONIBLE` | No se pudieron obtener las claves de Keycloak para validar el token |
| 504 | `TIEMPO_AGOTADO` | El servicio destino no responde dentro del tiempo límite |
| 500 | `ERROR_INTERNO` | Fallo inesperado del gateway |

- `X-Correlation-Id`: si llega con un formato válido (`[A-Za-z0-9-]{1,64}`, el mismo que aceptan los servicios) se conserva; si falta o es inválido, se genera un UUID. Se envía al servicio destino y se devuelve en toda respuesta, incluidas las de error.
- Logs estructurados en JSON. Un registro por solicitud con `idCorrelacion`, método, ruta, servicio destino, código de respuesta, duración en milisegundos y `sub` (si hay token válido).
- Endpoint `/salud` con liveness y readiness. La readiness del gateway **no** depende de los microservicios: la caída de uno no debe sacar de servicio al gateway (RNF-08).

## 7. Calidad

- Toda regla de las secciones 4, 5 y 6 tiene al menos un test de integración con WireMock: enrutamiento por prefijo, reenvío sin reescritura, 401 por cada causa (sin token, firma, emisor, vencido), rutas públicas, CORS, `404`, `503`, `504`, correlación recibida y generada, y respuesta del servicio devuelta tal cual.
- Cobertura mínima: 80 % de líneas, medida con JaCoCo. El pipeline falla si baja.
- Ninguna tarea se da por terminada con tests fallando.
- El gateway suma poca latencia: la meta de RNF-05 (REST < 3 s) se cumple de punta a punta, no solo en el servicio.

## 8. Simplicidad

- No se construye nada que no esté en una spec.
- Cada dependencia nueva se justifica en el plan.
- Nada de filtros, rutas ni configuraciones "por si acaso".

## 9. Convenciones

- Se adopta completa la sección «Convenciones» común de los microservicios: nombres en español sin tildes ni ñ, Conventional Commits, fechas ISO 8601 UTC y las excepciones en inglés que esa sección enumera.
- El pipeline vive en `.github/workflows/api-gateway.yml`, en la raíz, y se filtra por `servicios/api-gateway/**` (RNF-20).
- El gateway se levanta en local con Docker Compose, perfil `gateway` (RNF-19).

### Glosario de este servicio

| Concepto | Clase / archivo | Variable de entorno |
|---|---|---|
| Ruta a un microservicio o al servidor GraphQL | `application.yml` | `GESTION_URL`, `INVENTARIO_URL`, `OPERACIONES_URL`, `IA_URL`, `GRAPHQL_URL` |
| Validación del token | `ConfiguracionSeguridad` | `KEYCLOAK_JWKS_URI`, `KEYCLOAK_ISSUER` |
| Orígenes CORS | `application.yml` | `CORS_ORIGENES_PERMITIDOS` |
| Tiempo límite de respuesta | `application.yml` | `GATEWAY_TIEMPO_LIMITE`, `GATEWAY_TIEMPO_LIMITE_SINCRONIZACION` |
| Correlación | `FiltroIdCorrelacion` | — |
| Registro de acceso | `RegistroAcceso` | — |
| Error del gateway | `RespuestaError`, `ManejadorErroresGateway` | — |

## Enmiendas

- Versión: 1.1.0 (2026-11-06)
- Cambiar una regla requiere actualizar este documento, registrar el motivo y subir la versión:
  - MAJOR: se elimina o redefine una regla.
  - MINOR: se agrega una regla.
  - PATCH: aclaraciones de redacción sin cambio de significado.

| Versión | Fecha | Motivo |
|---|---|---|
| 1.0.0 | 2026-11-04 | Versión inicial. El gateway valida firma, emisor y vigencia del token; audiencia y roles quedan en cada microservicio. |
| 1.1.0 | 2026-11-06 | Ruta `/api/graphql` hacia `graphql-server` (`GRAPHQL_URL`), para que React use una sola URL base y GraphQL reciba la misma validación del token, CORS y correlación que los microservicios. Origen: `specs/spec-ruta-graphql.md`. |
