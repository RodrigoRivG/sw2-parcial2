# Enrutamiento seguro — `api-gateway`

| Campo | Valor |
|---|---|
| Servicio | `api-gateway` |
| Archivo | `specs/spec-enrutamiento.md` |
| Estado | Implementada (2026-11-04) |
| Constitución | v1.0.0 |
| Trazabilidad | Módulo 9 · procesos 2, 3 y 12 · RF-27, RF-28 · RN-16 · RNF-01, RNF-02, RNF-03, RNF-05, RNF-08, RNF-19, RNF-20, RNF-22 |
| Depende de | Los tres servicios de negocio con su prefijo `/api/<servicio>/v1` (ya implementados). Keycloak solo para la prueba manual de punta a punta. |

Contenido:

1. [Spec](#1-spec): qué debe hacer el gateway.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Escenarios de usuario y pruebas

### Historia 1 — Llegar al microservicio correcto (Prioridad: P1)

Como microfrontend, aplicación móvil o servicio interno, quiero enviar todas mis solicitudes a una sola URL, para no conocer dónde vive cada microservicio.

**Por qué esta prioridad:** sin enrutamiento, `servicio-operaciones` no puede consultar el estado de una campaña en `servicio-gestion` y la Saga no se puede probar de punta a punta.

**Prueba independiente:** con los servicios destino simulados, cada prefijo llega a su servicio con la ruta, la query, el cuerpo y los headers intactos.

**Escenarios de aceptación:**

1. **Dado** un token válido, **cuando** se envía `GET /api/gestion/v1/campanias/{id}/estado?x=1`, **entonces** `servicio-gestion` recibe exactamente `GET /api/gestion/v1/campanias/{id}/estado?x=1` con el mismo header `Authorization`, y el cliente recibe su respuesta sin cambios (código, headers y cuerpo).
2. Lo mismo para `/api/inventario/**`, `/api/operaciones/**` y `/api/ia/**`, cada uno hacia su servicio.
3. **Dado** un token válido, **cuando** se envía un `POST /api/operaciones/v1/incidencias` con `multipart/form-data` (fotografía), **entonces** el servicio recibe el cuerpo completo, byte a byte.
4. **Dado** que el servicio responde `422` con su `RespuestaError`, **cuando** el gateway la reenvía, **entonces** el cliente recibe el mismo `422` y el mismo cuerpo.
5. **Dado** un token válido, **cuando** se envía `GET /api/desconocido/v1/x` o `GET /otra-ruta`, **entonces** se responde `404 RUTA_NO_ENCONTRADA` y no se llama a ningún servicio.

### Historia 2 — Rechazar solicitudes sin un token válido (Prioridad: P1)

Como responsable del sistema, quiero que el gateway rechace los tokens inválidos antes de que lleguen a los servicios, para cumplir el Módulo 9 ("validando los tokens de Keycloak").

**Prueba independiente:** con un JWKS simulado, tokens inválidos por cada causa reciben 401 y el servicio destino no recibe ninguna solicitud.

**Escenarios de aceptación:**

1. **Dado** una solicitud a `/api/**` sin header `Authorization`, **entonces** se responde `401 NO_AUTENTICADO` y el servicio no es llamado.
2. **Dado** un token firmado con una clave que no está en el JWKS, **entonces** `401 NO_AUTENTICADO`.
3. **Dado** un token con un `iss` distinto de `KEYCLOAK_ISSUER`, **entonces** `401 NO_AUTENTICADO`.
4. **Dado** un token vencido (`exp` en el pasado), **entonces** `401 NO_AUTENTICADO`.
5. **Dado** un token válido cuyo `aud` no incluye el servicio destino, **entonces** el gateway lo reenvía (la audiencia la valida el servicio).
6. **Dado** un token válido sin ningún rol, **entonces** el gateway lo reenvía (los roles los valida el servicio, RN-16).
7. **Dado** una solicitud a `/salud`, `/salud/liveness` o `/salud/readiness` sin token, **entonces** responde `200` con estado `UP`.

### Historia 3 — Seguir funcionando aunque un servicio caiga (Prioridad: P1)

Como usuario de un microfrontend, quiero que la caída de un microservicio no impida usar los demás, y recibir un error claro en vez de una espera indefinida (RNF-08).

**Escenarios de aceptación:**

1. **Dado** que `servicio-inventario` no acepta conexiones (o, en Docker Compose, su contenedor está apagado y su nombre no se resuelve), **cuando** se envía una solicitud a `/api/inventario/**`, **entonces** se responde `503 SERVICIO_NO_DISPONIBLE`, y una solicitud simultánea a `/api/gestion/**` responde normalmente.
2. **Dado** que un servicio tarda más que el tiempo límite, **entonces** se responde `504 TIEMPO_AGOTADO` en cuanto se cumple ese tiempo.
4. **Dado** un lote de sincronización (`POST /api/operaciones/v1/sincronizacion`) que tarda 15 s porque `servicio-gestion` está caído, **entonces** el gateway no lo corta: esa ruta tiene su propio tiempo límite, más largo (ver 2.2).
3. **Dado** que ningún microservicio está levantado, **entonces** `/salud/readiness` del gateway sigue respondiendo `UP`.

### Historia 4 — Seguir una solicitud de punta a punta (Prioridad: P2)

Como desarrollador, quiero que toda solicitud lleve un identificador de correlación, para seguirla en los logs del gateway y del servicio (RNF-22).

**Escenarios de aceptación:**

1. **Dado** una solicitud con `X-Correlation-Id: abc-123`, **entonces** el servicio recibe `abc-123` y la respuesta lo devuelve.
2. **Dado** una solicitud sin `X-Correlation-Id`, o con uno inválido (por ejemplo, de 65 caracteres o con espacios), **entonces** el gateway genera un UUID, lo envía al servicio y lo devuelve en la respuesta.
3. **Dado** cualquier error del gateway (401, 404, 503, 504), **entonces** el cuerpo lleva el mismo `idCorrelacion` que el header de la respuesta.
4. **Dado** cualquier solicitud, **entonces** el gateway escribe un solo log JSON con `idCorrelacion`, método, ruta, servicio destino, código, duración y `sub` (si el token era válido), sin el token.

### Historia 5 — Llamar al backend desde los microfrontends (Prioridad: P2)

Como microfrontend publicado en otro origen (S3 + CloudFront, o `localhost` con otro puerto en desarrollo), quiero que el navegador permita mis solicitudes al gateway.

**Escenarios de aceptación:**

1. **Dado** un origen incluido en `CORS_ORIGENES_PERMITIDOS`, **cuando** el navegador envía una solicitud `OPTIONS` de verificación previa sin token, **entonces** se responde `200` con `Access-Control-Allow-Origin` igual a ese origen, y con los métodos y headers permitidos.
2. **Dado** un origen no incluido, **entonces** la verificación previa se rechaza (`403`, sin headers de CORS).
3. **Dado** una solicitud real desde un origen permitido, **entonces** la respuesta incluye `Access-Control-Allow-Origin` y expone `X-Correlation-Id`.

### Casos borde

- **Keycloak no responde y el gateway todavía no tiene las claves:** se responde `503 AUTENTICACION_NO_DISPONIBLE`, no `401`. El cliente no debe pensar que su sesión venció.
- **Header `Authorization` con un esquema distinto de `Bearer`, o un token mal formado:** `401 NO_AUTENTICADO`.
- **El prefijo debe coincidir completo:** `/api/gestionx/v1` no va a `servicio-gestion` (`404 RUTA_NO_ENCONTRADA`).
- **El servicio destino corta la conexión a mitad de la respuesta:** no se reintenta. El cliente recibe el error de conexión o un `503 SERVICIO_NO_DISPONIBLE` si los headers aún no se habían enviado.
- **Un servicio devuelve sus propios headers de CORS:** hoy ninguno lo hace. Si alguno los agrega, la respuesta no debe llevar el header duplicado.
- **Cuerpos grandes:** el lote de sincronización admite hasta 40 MB y una incidencia, una foto de hasta 10 MB (`spec-sincronizacion.md` RQ-SIN-01, `spec-incidencias.md` RQ-INC-02). El gateway reenvía el cuerpo en streaming, sin cargarlo en memoria ni imponer un límite propio; los límites los aplica cada servicio.
- **Header `Location` de los `201`:** `servicio-gestion` y `servicio-inventario` lo devuelven relativo (`/api/...`) y llega bien al cliente. `servicio-operaciones` lo arma con `url()` de Laravel, que usa el host de la solicitud: detrás del gateway devolvería `http://servicio-operaciones:8000/...`, una URL interna. Se corrige en `servicio-operaciones` (ver 1.6), no en el gateway.

## 1.2 Requisitos

### Requisitos funcionales

- **RF-GW-01:** enrutar por prefijo según la tabla de la constitución §4, sin reescribir la ruta.
- **RF-GW-02:** reenviar sin cambios el método, la query, el cuerpo, los headers (incluido `Authorization`) y la respuesta del servicio.
- **RF-GW-03:** validar firma, `iss` y `exp` del JWT en toda ruta `/api/**`. No validar `aud` ni roles.
- **RF-GW-04:** responder `404 RUTA_NO_ENCONTRADA` a toda ruta sin destino.
- **RF-GW-05:** responder `503 SERVICIO_NO_DISPONIBLE` si el destino rechaza la conexión, y `504 TIEMPO_AGOTADO` si no responde dentro del tiempo límite.
- **RF-GW-06:** conservar o generar `X-Correlation-Id`, enviarlo al destino y devolverlo en toda respuesta.
- **RF-GW-07:** aplicar CORS con la lista de orígenes de `CORS_ORIGENES_PERMITIDOS`.
- **RF-GW-08:** exponer `/salud`, `/salud/liveness` y `/salud/readiness` sin token, sin depender de los microservicios.
- **RF-GW-09:** escribir un log JSON por solicitud con los campos de la historia 4.

### Entidades clave

El gateway no tiene entidades ni persistencia. Su único dato propio es `RespuestaError`.

## 1.3 Permisos

| Ruta | Acceso |
|---|---|
| `/api/**` | Cualquier token válido de Keycloak (usuario o cuenta de servicio). Los permisos los verifica cada servicio. |
| `OPTIONS` de CORS sobre `/api/**` | Sin token |
| `/salud`, `/salud/liveness`, `/salud/readiness` | Sin token |

## 1.4 Errores de esta funcionalidad

| HTTP | `codigo` | `mensaje` |
|---|---|---|
| 401 | `NO_AUTENTICADO` | "Debe iniciar sesión para continuar." |
| 404 | `RUTA_NO_ENCONTRADA` | "La ruta solicitada no existe." |
| 503 | `SERVICIO_NO_DISPONIBLE` | "El servicio solicitado no está disponible en este momento." |
| 503 | `AUTENTICACION_NO_DISPONIBLE` | "No se pudo verificar la sesión. Intente nuevamente en unos minutos." |
| 504 | `TIEMPO_AGOTADO` | "El servicio tardó demasiado en responder." |
| 500 | `ERROR_INTERNO` | "Ocurrió un error inesperado." |

## 1.5 Criterios de éxito

- **CE-GW-01:** los escenarios de las historias 1 a 5 pasan como tests de integración automatizados.
- **CE-GW-02:** la latencia que agrega el gateway, medida contra un destino simulado que responde al instante, tiene un p95 menor a 50 ms en 100 solicitudes seguidas, para que la meta de RNF-05 (REST < 3 s) dependa solo del servicio.
- **CE-GW-03:** con el perfil `saga` y Keycloak levantados, `servicio-operaciones` consulta el estado de una campaña a través del gateway (prueba manual, ver T12).
- **CE-GW-04:** la cobertura de líneas es ≥ 80 %.

## 1.6 Supuestos

- Los microservicios ya validan su propio token (firma, `iss`, `aud`, `exp` y roles). El gateway es una primera barrera, no la única.
- El TLS de la nube lo termina Azure Container Apps; en local todo es HTTP dentro de la red de Docker.
- Los orígenes de los microfrontends en desarrollo aún no existen. El valor local de `CORS_ORIGENES_PERMITIDOS` es provisional y se ajusta cuando se cree la aplicación contenedora de single-spa.
- El realm `agro` con roles, clients y Audience mappers se define en una spec aparte, en la raíz del repositorio. Esta spec no depende de él para sus tests.
- **Contrato con `servicio-operaciones`** (`servicio-operaciones/specs/README.md` D-12 y `spec-labores.md` RQ-LAB-05): consulta la campaña con un tiempo límite propio de 2 s y un solo intento. Solo un `404` con `codigo = CAMPANIA_NO_ENCONTRADA` significa "campaña inexistente"; el `404 RUTA_NO_ENCONTRADA`, el `401`, el `503` y el `504` del gateway cuentan como "no disponible" y dejan la labor con validación diferida. Por eso el gateway nunca debe devolver `CAMPANIA_NO_ENCONTRADA` ni reescribir el cuerpo de un `404` del servicio.
- **Correlación compatible:** el formato que acepta el gateway (`[A-Za-z0-9-]{1,64}`) es igual o más estricto que el de los tres servicios (gestión `[A-Za-z0-9-]{1,64}`, inventario `[\w-]{1,64}`, operaciones `[A-Za-z0-9._-]{1,100}`). Así ningún servicio reemplaza el id que le llega del gateway.
- **Location de `servicio-operaciones`:** antes de T12 se cambia `url(...)` por una ruta relativa en `LaborControlador` e `IncidenciaControlador` (dos líneas y sus tests), igual que gestión e inventario. Es un cambio en otro servicio y se hace en su propio commit.

## 1.7 Aclaraciones

- **¿Por qué el gateway no valida `aud`?** Un mismo token de usuario se usa para varios servicios, y cada uno exige su propia audiencia. Si el gateway la validara, tendría que conocer qué audiencia corresponde a cada prefijo, una regla que ya cumple cada servicio.
- **¿Por qué no hay reintentos?** Un `POST` reintentado por el gateway podría duplicar una operación. La sincronización offline ya reintenta desde el cliente con idempotencia por UUID (RN-10).

## 1.8 Fuera de alcance

- Rate limiting, circuit breaker, caché y balanceo (constitución §1).
- Exponer la documentación OpenAPI o la salud de los microservicios a través del gateway.
- El servidor GraphQL (`graphql-server`): es un cliente más del gateway, no una ruta de él.
- La creación del realm de Keycloak.

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución. Las rutas y la política de CORS en `application.yml`; Java solo donde la configuración no alcanza.

**Documentos que debe tener a mano quien implemente:** la constitución del gateway v1.0.0 (`servicios/api-gateway/Constitucion.md`) y este archivo.

**Coordenadas del proyecto:** `groupId` `com.agrosystem`, `artifactId` `api-gateway`, paquete raíz `com.agrosystem.gateway`.

## 2.1 Dependencias (`pom.xml`)

| Dependencia | Para qué |
|---|---|
| Spring Boot 3.4 (parent, el mismo patch que `servicio-gestion`), Java 21 | Base; logs JSON nativos |
| BOM `spring-cloud-dependencies` 2024.0.x (la línea compatible con Boot 3.4) | Versiones de Spring Cloud |
| `spring-cloud-starter-gateway` | Gateway reactivo (WebFlux + Reactor Netty) |
| `spring-boot-starter-oauth2-resource-server` | Validación del JWT (reactiva) |
| `spring-boot-starter-actuator` | `/salud` |
| `spring-boot-devtools` (opcional, fuera de la imagen final) | Recarga en caliente en Docker Compose |
| Test: `spring-boot-starter-test`, `spring-security-test`, `org.wiremock:wiremock-standalone` 3.x | Tests de integración con destinos y JWKS simulados |
| Plugin `jacoco-maven-plugin` (mismo que `servicio-gestion`) | Cobertura mínima del 80 % |

No se agrega `spring-boot-starter-web`: el gateway reactivo no funciona con Spring MVC en el classpath.

Los tokens de los tests se firman con Nimbus JOSE (`com.nimbusds:nimbus-jose-jwt`), que ya llega como dependencia del resource server; no se declara aparte.

## 2.2 Configuración (`application.yml`)

| Variable | Uso | Valor local (Docker Compose) |
|---|---|---|
| `SERVER_PORT` | Puerto HTTP | `8080` |
| `GESTION_URL`, `INVENTARIO_URL`, `OPERACIONES_URL`, `IA_URL` | `uri` de cada ruta | Ya definidas en `docker-compose.yml` |
| `KEYCLOAK_JWKS_URI` | `spring.security.oauth2.resourceserver.jwt.jwk-set-uri` | Ya definida (`x-keycloak-env`) |
| `KEYCLOAK_ISSUER` | `spring.security.oauth2.resourceserver.jwt.issuer-uri` (solo se compara con `iss`) | Ya definida |
| `CORS_ORIGENES_PERMITIDOS` | Lista separada por comas | Provisional: `http://localhost:9000` |
| `GATEWAY_TIEMPO_LIMITE` | `spring.cloud.gateway.httpclient.response-timeout` (todas las rutas) | Por defecto `10s` |
| `GATEWAY_TIEMPO_LIMITE_SINCRONIZACION` | `metadata.response-timeout` de la ruta de sincronización, en milisegundos | Por defecto `120000` |

Valores fijos:

- Rutas en `spring.cloud.gateway.routes`, una por servicio, con el predicado `Path=/api/<servicio>/**` y sin filtros de reescritura. Ids de ruta: `servicio-gestion`, `servicio-inventario`, `servicio-operaciones`, `servicio-ia` (se usan como "servicio destino" en el log).
- Una quinta ruta, `operaciones-sincronizacion`, con `Path=/api/operaciones/v1/sincronizacion`, el mismo destino que `servicio-operaciones`, `order: -1` (para que gane a la ruta general) y su propio `response-timeout`. Motivo: un lote de 50 operaciones tarda unos 11 s con gestión caída (`spec-sincronizacion.md` CE-SIN-03 permite 15 s) y, en el peor caso de 50 campañas distintas, hasta 100 s (2 s por campaña). En el log, su servicio destino se informa como `servicio-operaciones`.
- `spring.cloud.gateway.httpclient.connect-timeout: 2000` (ms).
- `spring.cloud.gateway.default-filters: DedupeResponseHeader=Access-Control-Allow-Origin Access-Control-Allow-Credentials, RETAIN_FIRST` (caso borde de CORS duplicado).
- El tiempo límite general de 10 s cubre una foto de 10 MB (CE-INC-04 pide menos de 3 s) y deja margen sobre la meta de RNF-05. El de Reactor Netty empieza a contar cuando terminó de enviarse la solicitud, así que la subida lenta de un lote desde una red móvil no lo consume.
- `logging.structured.format.console: ecs`.
- Actuator igual que en `servicio-gestion`: `base-path: /`, `path-mapping.health: salud`, solo `health` expuesto y `probes.enabled: true`. La readiness incluye solo `readinessState` (RNF-08).

Si `KEYCLOAK_JWKS_URI` o `KEYCLOAK_ISSUER` faltan, la aplicación no arranca (RNF-03).

## 2.3 Seguridad (`ConfiguracionSeguridad`)

- `SecurityWebFilterChain` reactivo, sin sesión, sin CSRF, sin login por formulario ni HTTP Basic.
- `permitAll` para `/salud/**` y para `OPTIONS /api/**`. `authenticated()` para `/api/**`. Para cualquier otra ruta, `permitAll`: así llega al gateway y responde `404 RUTA_NO_ENCONTRADA`, en vez de un 401 que confunda.
- `oauth2ResourceServer().jwt()` con el decodificador que arma Spring Boot a partir de `jwk-set-uri` e `issuer-uri`: valida firma, `iss` y `exp`. No se configuran `audiences`.
- El punto de entrada de autenticación (`ServerAuthenticationEntryPoint`) escribe `401 NO_AUTENTICADO` con `RespuestaError`.
- Si el JWKS no se puede descargar, Spring Security lanza `AuthenticationServiceException`; `ManejadorErroresGateway` la traduce a `503 AUTENTICACION_NO_DISPONIBLE`.
- CORS en la cadena de seguridad (`http.cors(...)`) con un `CorsConfigurationSource` construido desde `CORS_ORIGENES_PERMITIDOS`, para que la verificación previa se resuelva antes de exigir el token:
  - Métodos: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`.
  - Headers permitidos: `Authorization`, `Content-Type`, `X-Correlation-Id`.
  - Header expuesto: `X-Correlation-Id`.
  - Sin credenciales (los frontends envían el token en `Authorization`, no en cookies).
  - `maxAge` de 1 hora.

## 2.4 Correlación y log de acceso

- **`FiltroIdCorrelacion`** (`WebFilter` con la máxima precedencia, antes de la seguridad):
  - Valida el header recibido con `[A-Za-z0-9-]{1,64}`; si falta o no coincide, genera un UUID.
  - Reemplaza el header en la solicitud (con `exchange.mutate()`), para que el destino lo reciba; lo agrega a la respuesta y lo guarda como atributo del exchange (`idCorrelacion`) para el manejador de errores y el log.
- **`RegistroAcceso`** (`WebFilter` justo después de `FiltroIdCorrelacion`, también antes de la seguridad, para registrar los 401):
  - Al terminar la respuesta (`doFinally`), escribe un log `INFO` con pares clave-valor de SLF4J: `idCorrelacion`, `metodo`, `ruta` (sin query), `servicioDestino` (id de la ruta o `ninguno`), `estado`, `duracionMs` y `sub`.
  - El `sub` lo guarda en un atributo del exchange un `WebFilter` que corre después de la seguridad (`exchange.getPrincipal()`). Los atributos se comparten entre los decoradores del exchange, así que `RegistroAcceso` los lee al final.
  - Nunca registra headers ni el cuerpo.

## 2.5 Errores (`RespuestaError`, `ManejadorErroresGateway`)

- `RespuestaError`: `record` con `codigo`, `mensaje`, `detalles` (lista vacía) e `idCorrelacion`; se serializa igual que en `servicio-gestion`.
- `ManejadorErroresGateway`: `ErrorWebExceptionHandler` con `@Order(-2)` (antes del manejador por defecto de Boot). Responde `application/json`, sin trazas:

  | Excepción | HTTP | Código |
  |---|---|---|
  | `ResponseStatusException` 404 (sin ruta) o `NoResourceFoundException` | 404 | `RUTA_NO_ENCONTRADA` |
  | `java.net.ConnectException`, `io.netty.channel.ConnectTimeoutException` o `java.net.UnknownHostException` (también si vienen como causa) | 503 | `SERVICIO_NO_DISPONIBLE` |
  | `ResponseStatusException` 504 (lo lanza el gateway al agotar `response-timeout`) | 504 | `TIEMPO_AGOTADO` |
  | `AuthenticationServiceException` | 503 | `AUTENTICACION_NO_DISPONIBLE` |
  | Cualquier otra | 500 | `ERROR_INTERNO` |

- Si la respuesta ya se había empezado a enviar, no se escribe cuerpo (caso borde de conexión cortada).

## 2.6 Tests

Todos en `src/test/java/com/agrosystem/gateway/integration/`, con `@SpringBootTest(webEnvironment = RANDOM_PORT)` y `WebTestClient`.

- **`PruebaIntegracionBase`**:
  - Levanta un WireMock que hace de los cuatro servicios y de Keycloak.
  - Genera un par de claves RSA, publica el JWKS en WireMock y ofrece un método para firmar tokens con `iss`, `exp`, `sub` y `aud` configurables (más una segunda clave que no está en el JWKS).
  - Con `@DynamicPropertySource` apunta `GESTION_URL`, `INVENTARIO_URL`, `OPERACIONES_URL`, `IA_URL` y `KEYCLOAK_JWKS_URI` a WireMock, y fija `GATEWAY_TIEMPO_LIMITE=1s`.
- **`EnrutamientoIT`**: historia 1 (los cuatro prefijos, query, multipart byte a byte, headers, respuesta 4xx devuelta tal cual, prefijo incompleto y ruta desconocida → 404 sin llamadas a WireMock).
- **`SeguridadIT`**: historia 2 (sin token, otra clave, otro `iss`, vencido, `aud` ajeno y sin roles reenviados, esquema distinto de `Bearer`, salud sin token) y el caso de JWKS no disponible (WireMock responde 500 al JWKS, decodificador sin claves en caché) → `503 AUTENTICACION_NO_DISPONIBLE`.
- **`ResilienciaIT`**: historia 3 (una ruta apuntando a un puerto sin servicio → 503; demora de WireMock de 2 s → 504; la misma demora en `/api/operaciones/v1/sincronizacion`, con `GATEWAY_TIEMPO_LIMITE_SINCRONIZACION=3000` en el test, responde `200`; readiness `UP` con el destino caído). En `EnrutamientoIT`, un `404` de WireMock con `CAMPANIA_NO_ENCONTRADA` llega intacto al cliente.
- **`CorrelacionIT`**: historia 4 (recibido, ausente, inválido; mismo id en header y cuerpo de error; el destino lo recibe). El log se verifica con un `OutputCaptureExtension` buscando `idCorrelacion` y la ausencia del token.
- **`CorsIT`**: historia 5 (verificación previa permitida y rechazada, header expuesto, sin duplicados cuando WireMock devuelve su propio `Access-Control-Allow-Origin`).
- **`LatenciaIT`**: CE-GW-02 (100 solicitudes contra un destino sin demora; p95 < 50 ms tras un calentamiento de 20).

## 2.7 Empaquetado, entorno y pipeline

- **`Dockerfile`** igual al de `servicio-gestion` (build con Maven, imagen `eclipse-temurin:21-jre`, usuario sin privilegios) con el jar `api-gateway-*.jar`. **`.dockerignore`**: `target`, `specs`, `Constitucion.md`.
- **`.github/workflows/api-gateway.yml`** en la raíz, copia de `servicio-gestion.yml` con las rutas cambiadas: `mvn -B verify` y build de la imagen.
- **`docker-compose.yml`**: agregar `CORS_ORIGENES_PERMITIDOS` al servicio `api-gateway`. Los perfiles no cambian: la prueba de punta a punta ya está definida con `--profile saga --profile gateway --profile auth` (`servicio-operaciones/specs/spec-saga.md` CE-SAG-05).
- **`README.md`**: actualizar la lista de servicios con código y la fila de variables de `api-gateway`.

## 2.8 Decisiones del plan

| ID | Decisión | Motivo |
|---|---|---|
| D-GW-01 | Spring Cloud Gateway reactivo, no la variante Server MVC | Es la variante de referencia, sin un hilo bloqueado por solicitud y sin configuración extra. El mismo `-Xmx384m` de Docker Compose alcanza. |
| D-GW-02 | CORS en la cadena de seguridad, no en `spring.cloud.gateway.globalcors` | La seguridad corre antes que el gateway y rechazaría con 401 la verificación previa, que no lleva token. |
| D-GW-03 | Rutas sin destino en `permitAll` | Responder 404 a una ruta inexistente, en vez de 401, es lo que espera quien se equivocó de URL. |
| D-GW-04 | Tests con WireMock y tokens firmados en el test, sin Testcontainers | No hay base de datos ni broker; un contenedor de Keycloak sumaría casi un minuto por ejecución sin probar nada que el JWKS simulado no pruebe. |
| D-GW-05 | Tiempo límite general de 10 s y uno propio de 120 s para la sincronización, ambos configurables | La sincronización es la única ruta cuyo tiempo de respuesta, según su spec, puede superar los 10 s. |
| D-GW-06 | Sin límite de tamaño de cuerpo en el gateway | Cada servicio ya aplica el suyo (40 MB el lote, 10 MB la foto); duplicarlo obligaría a mantener dos valores iguales. |

### Notas de implementación (2026-11-04)

- **Decodificador JWT propio** (`ConfiguracionSeguridad.decodificadorJwt`), en lugar del que arma Spring Boot: es el mismo (`jwk-set-uri` + validador de `iss`), pero si el JWKS no se puede descargar, Nimbus lanza `IllegalStateException("Could not obtain the keys")`, que no pasa por Spring Security y terminaba en `500`. El decodificador lo convierte en `JwtException`; Spring Security lo transforma en `AuthenticationServiceException` y el manejador responde `503 AUTENTICACION_NO_DISPONIBLE`. Lo detectó `AutenticacionNoDisponibleIT`.
- **Servicio destino en el log:** cada ruta lleva `metadata.servicio`, así la ruta de sincronización se informa como `servicio-operaciones` sin una tabla de equivalencias en el código.
- **Log de acceso al confirmar la respuesta** (`beforeCommit`) y no al terminar la cadena de filtros: los errores del gateway (404, 503, 504) se resuelven fuera de esa cadena, y al terminarla el estado aún no estaba fijado.
- **`ResponseStatusException` 4xx distintas de 404** (por ejemplo, una solicitud mal formada que rechaza Netty) responden con su mismo código HTTP y `codigo = DATOS_INVALIDOS`, el código común de los servicios para entradas inválidas.
- **CORS rechazado:** el `403` de una verificación previa desde un origen no permitido lo escribe Spring sin cuerpo. Es una respuesta para el navegador, que no la expone al código del frontend.
- **Nombre que no se resuelve → 503:** en Docker Compose, el nombre de un contenedor apagado deja de existir y el error es `UnknownHostException`, no `ConnectException`; respondía `500`. Lo detectó `scripts/verificar-realm.py` con los servicios apagados; lo cubre `ResilienciaIT`.
- `CodigoError` y `EscritorRespuestaError` se agregaron al paquete `web` para no repetir códigos y mensajes entre el manejador de errores y el punto de entrada 401.

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

- [x] **T01** — Crear el proyecto Maven (`pom.xml`, `AplicacionGateway.java`) con las dependencias de 2.1 y la estructura de la constitución. *Hecho cuando:* `./scripts/ejecutar.sh api-gateway mvn -B verify` compila.
- [x] **T02** — Escribir `application.yml` (rutas, tiempos límite, logs JSON y Actuator) y `PruebaIntegracionBase`. *Hecho cuando:* `/salud`, `/salud/liveness` y `/salud/readiness` responden `UP` sin ningún servicio levantado.
- [x] **T03** — Implementar `RespuestaError` y `ManejadorErroresGateway`. *Hecho cuando:* pasan los escenarios 404 de `EnrutamientoIT` y los 503/504 de `ResilienciaIT`.
- [x] **T04** — Implementar `FiltroIdCorrelacion`. *Hecho cuando:* pasa `CorrelacionIT`, salvo la verificación del log.
- [x] **T05** — Implementar `ConfiguracionSeguridad` con el punto de entrada 401 y la traducción a `AUTENTICACION_NO_DISPONIBLE`. *Hecho cuando:* pasa `SeguridadIT`.
- [x] **T06** — Completar `EnrutamientoIT` (reenvío intacto, multipart, respuestas 4xx). *Hecho cuando:* pasa completo.
- [x] **T07** [P] — Agregar CORS a la cadena de seguridad y el filtro `DedupeResponseHeader`. *Hecho cuando:* pasa `CorsIT`.
- [x] **T08** [P] — Implementar `RegistroAcceso` y el filtro que guarda el `sub`. *Hecho cuando:* pasa la verificación del log en `CorrelacionIT` (campos presentes, sin token).
- [x] **T09** [P] — Escribir `LatenciaIT` (CE-GW-02).
- [x] **T10** — Escribir el `Dockerfile`, `.dockerignore` y `.github/workflows/api-gateway.yml`, con JaCoCo al 80 %. *Hecho cuando:* `mvn -B verify` pasa con la cobertura y `docker build` construye la imagen.
- [x] **T11** — Actualizar `docker-compose.yml` (`CORS_ORIGENES_PERMITIDOS`) y `README.md`. *Hecho cuando:* `docker compose --profile gateway up -d api-gateway` arranca y `curl localhost:8080/salud` responde `UP`, y `curl localhost:8080/api/gestion/v1/parcelas` sin token responde `401 NO_AUTENTICADO`.
- [x] **T12** — Prueba manual de punta a punta (CE-GW-03, requiere el realm de Keycloak y la corrección del `Location` de operaciones, ver 1.6): con los perfiles `saga`, `gateway` y `auth`, un token de usuario obtenido de Keycloak llega a los tres servicios a través del gateway, y la consulta de `servicio-operaciones` a `GET /api/gestion/v1/campanias/{id}/estado` responde con el estado de la campaña. *Hecho cuando:* los dos casos quedan comprobados con `curl` y en los logs aparece el mismo `idCorrelacion` en el gateway y en el servicio.
- [x] **T13** — Verificación final: `mvn -B verify` en verde, cobertura ≥ 80 % y los criterios CE-GW-01, CE-GW-02 y CE-GW-04 cubiertos por al menos un test. Resultado: 42 tests en verde y cobertura ≥ 80 %. T12 comprobada con `scripts/verificar-realm.py --saga` (`specs/spec-keycloak-realm.md`, Resultado).
