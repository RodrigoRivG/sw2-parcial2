# Base del servicio — `servicio-ia`

| Campo | Valor |
|---|---|
| Servicio | `servicio-ia` |
| Archivo | `specs/spec-base.md` |
| Estado | Spec en borrador · Plan y tareas en borrador |
| Fecha | 2026-11-04 |
| Constitución | v3.0.0 (secciones 2, 3, 7, 8, 9, 11, 12 y 13) |
| Trazabilidad | Soporte de CU-14 a CU-18 y CU-25 · RN-14, RN-16 · RNF-02, RNF-03, RNF-08, RNF-18, RNF-19, RNF-20, RNF-22 |
| Depende de | API Gateway (ruta `/api/ia/**`, ya implementada) y realm `agro` (client `servicio-ia`, ya implementado). Ninguno se necesita para los tests automáticos. |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Contexto

Esta spec no entrega funcionalidad de IA. Construye lo que las cinco specs siguientes reutilizan: el proyecto, la configuración, la seguridad, el formato de errores, la correlación, los logs, la salud, el empaquetado y el cliente de solo lectura hacia los demás microservicios.

Quién llama a este servicio y a quién llama él:

| Dirección | Quién | Cómo |
|---|---|---|
| Entrada | React, Vue.js, Flutter, GraphQL y n8n | A través del API Gateway, con token de usuario o de cuenta de servicio, audiencia `servicio-ia` |
| Salida | `servicio-gestion`, `servicio-inventario` y `servicio-operaciones` | A través del API Gateway, con el token de la cuenta de servicio `servicio-ia`, solo lecturas |

## 1.2 Escenarios de usuario y pruebas

### Historia 1 — Saber si el servicio está listo (Prioridad: P1)

Como Docker Compose, Cloud Run o el desarrollador, quiero consultar la salud del servicio sin token, para saber si puede recibir solicitudes.

**Por qué esta prioridad:** sin salud, Docker Compose y Cloud Run no saben cuándo enviar tráfico.

**Prueba independiente:** con la aplicación levantada en el `TestClient`, sin token.

**Escenarios de aceptación:**

1. **Dado** el servicio iniciado, **cuando** se consulta `/salud/liveness`, **entonces** responde `200 { "estado": "UP" }`.
2. **Dado** el servicio iniciado, **cuando** se consulta `/salud/readiness` o `/salud`, **entonces** responde `200` con `estado = UP` y la lista de comprobaciones (vacía en esta spec).
3. **Dado** una comprobación crítica registrada que falla, **entonces** readiness responde `503` con `estado = DOWN` y el componente que falló.
4. **Dado** una comprobación informativa (Ollama, desde `spec-agentes.md`) que falla, **entonces** readiness sigue en `200 UP` e informa el componente como `DOWN` en `informativos` (constitución §11).
5. **Dado** que `servicio-gestion` está caído, **entonces** readiness sigue en `UP`: los demás microservicios no forman parte de la salud (RNF-08).

---

### Historia 2 — Rechazar solicitudes sin un token válido o sin el rol (Prioridad: P1)

Como responsable del sistema, quiero que toda ruta del prefijo `/api/ia/v1` exija un JWT de Keycloak válido para este servicio y el rol que corresponda, aunque la solicitud ya haya pasado por el gateway (RNF-02, RN-16).

**Prueba independiente:** con una clave RSA local en lugar del JWKS de Keycloak y una ruta de prueba protegida con el rol `gerencia`, registrada solo en los tests.

**Escenarios de aceptación:**

1. **Dado** una solicitud sin `Authorization`, **entonces** `401 NO_AUTENTICADO`.
2. **Dado** un token firmado con una clave que no está en el JWKS, con `iss` distinto de `KEYCLOAK_ISSUER`, vencido o sin `servicio-ia` en `aud`, **entonces** `401 NO_AUTENTICADO` en cada caso.
3. **Dado** un token válido sin el rol `gerencia`, **entonces** `403 SIN_PERMISO`.
4. **Dado** un token válido con `gerencia` (o con `gerencia` y `administrador`), **entonces** la ruta recibe un usuario con `id` = `sub`, su nombre y sus roles de `realm_access.roles`.
5. **Dado** que Keycloak no responde y todavía no hay claves en caché, **entonces** `503 AUTENTICACION_NO_DISPONIBLE`, no `401`.
6. **Dado** un token con un `kid` nuevo (Keycloak rotó las claves), **entonces** el servicio vuelve a descargar el JWKS una vez y lo acepta si la clave está.

---

### Historia 3 — Recibir errores con un formato común y poder seguirlos (Prioridad: P1)

Como frontend o desarrollador, quiero que todo error tenga el mismo formato que en los demás servicios y que cada solicitud lleve un identificador de correlación, para mostrar mensajes claros y seguirla en los logs (constitución §11, RNF-22).

**Prueba independiente:** con la aplicación en el `TestClient` y rutas de prueba que lanzan cada tipo de error.

**Escenarios de aceptación:**

1. **Dado** un cuerpo con un campo faltante, un tipo incorrecto, un número JSON en un campo decimal o JSON mal formado, **entonces** `400 DATOS_INVALIDOS` con un detalle `{ campo, mensaje }` por problema, y `campo` en camelCase.
2. **Dado** una ruta inexistente, **entonces** `404 RECURSO_NO_ENCONTRADO`; **dado** un método no soportado, `405 METODO_NO_PERMITIDO`.
3. **Dado** un error inesperado, **entonces** `500 ERROR_INTERNO` sin trazas en el cuerpo, y el error completo en el log con el `idCorrelacion`.
4. **Dado** una solicitud con `X-Correlation-Id: abc-123`, **entonces** la respuesta (también en 401, 403 y 500) devuelve `abc-123` en el header y en el cuerpo de error, y los logs de esa solicitud lo incluyen.
5. **Dado** una solicitud sin `X-Correlation-Id` o con uno inválido, **entonces** se genera un UUID.
6. **Dado** cualquier solicitud, **entonces** se escribe un log de acceso JSON con `idCorrelacion`, método, ruta, código, duración y `sub` (si hubo token válido), sin el token.

---

### Historia 4 — Consultar a los demás microservicios solo para leer (Prioridad: P1)

Como módulo de este servicio (entrenamiento, herramientas MCP), quiero un cliente que obtenga el token de la cuenta de servicio y consulte el gateway con tiempo límite, para leer datos de negocio sin poder modificarlos (RN-14) y sin quedar colgado si un servicio cae (RNF-08).

**Prueba independiente:** con `httpx.MockTransport` simulando Keycloak y el gateway.

**Escenarios de aceptación:**

1. **Dado** dos consultas seguidas, **entonces** se pide un solo token a Keycloak (caché) y ambas llevan `Authorization: Bearer <token>` y el `X-Correlation-Id` de la solicitud en curso.
2. **Dado** un token que vence en menos de 30 s, **entonces** se pide uno nuevo antes de la consulta.
3. **Dado** que el gateway responde `401`, **entonces** el cliente renueva el token y repite una sola vez; si vuelve a recibir `401`, falla como "no disponible" y registra el error.
4. **Dado** un `404` con un código del servicio (por ejemplo, `CAMPANIA_NO_ENCONTRADA`), **entonces** el cliente informa "no encontrado" con ese código. **Dado** un `404 RUTA_NO_ENCONTRADA` del gateway o `RECURSO_NO_ENCONTRADO` del servicio, **entonces** informa "no disponible": es un error de contrato, no un dato inexistente.
5. **Dado** un `503` o `504` del gateway, un `5xx` del servicio, un error de conexión, el tiempo límite agotado o una respuesta `2xx` que no es JSON, **entonces** informa "no disponible" sin reintentar.
6. **Dado** un `400`, `403`, `409` o `422`, **entonces** informa "rechazado" con el código recibido y lo registra como error (indica un error de este servicio o de los permisos del realm).
7. **Dado** que un módulo no maneja un "no disponible", **entonces** el cliente HTTP de este servicio recibe `503 DEPENDENCIA_NO_DISPONIBLE`; si no maneja un "no encontrado" o un "rechazado", `500 ERROR_INTERNO`.
8. **Dado** el cliente, **entonces** solo permite consultas `GET`: no tiene métodos para escribir.

### Casos borde

- **Keycloak no entrega el token de servicio** (caído, secreto incorrecto): la consulta falla como "no disponible"; el secreto nunca aparece en el log.
- **Varias consultas simultáneas sin token en caché:** se pide un solo token; las demás esperan ese mismo resultado.
- **Variable de entorno obligatoria vacía** (por ejemplo, `KEYCLOAK_CLIENT_SECRET` sin `.env`): el proceso no arranca y el log dice qué variable falta, sin mostrar valores.
- **Token con `aud` como texto en vez de lista:** se acepta si es `servicio-ia`.
- **Ruta del prefijo inexistente con token inválido:** `404 RECURSO_NO_ENCONTRADO` (la ruta se resuelve antes que la seguridad; el gateway ya validó el token).

## 1.3 Requisitos

### Requisitos funcionales

- **RQ-BASE-01:** exponer `/salud`, `/salud/liveness` y `/salud/readiness` sin token, con comprobaciones críticas e informativas que registran las specs siguientes.
- **RQ-BASE-02:** exigir en toda ruta de `/api/ia/v1` un JWT con firma válida según el JWKS de Keycloak, `iss` = `KEYCLOAK_ISSUER`, `aud` que contenga `KEYCLOAK_AUDIENCE` y `exp` vigente.
- **RQ-BASE-03:** ofrecer a las rutas una verificación de roles (`realm_access.roles`) que responda `403 SIN_PERMISO` si el usuario no tiene ninguno de los roles pedidos.
- **RQ-BASE-04:** responder todo error con `{ codigo, mensaje, detalles, idCorrelacion }` según el catálogo del README.
- **RQ-BASE-05:** conservar o generar `X-Correlation-Id`, devolverlo en toda respuesta y agregarlo a cada log.
- **RQ-BASE-06:** escribir logs JSON y un log de acceso por solicitud (README D-10).
- **RQ-BASE-07:** ofrecer un cliente de solo lectura hacia el gateway con token de cuenta de servicio, tiempo límite y la clasificación de errores de la Historia 4 (README D-08).
- **RQ-BASE-08:** ofrecer tipos comunes para decimales como texto, fechas UTC y esquemas en camelCase (README D-03, D-04 y D-06).
- **RQ-BASE-09:** no arrancar si falta una variable de entorno obligatoria.
- **RQ-BASE-10:** publicar el contrato OpenAPI en `/openapi.json` y `/docs`, sin token.

### Entidades clave

No hay entidades de negocio. Tipos propios: `UsuarioAutenticado` (`id`, `nombre`, `roles`), `RespuestaError`, `DetalleError` y `ErrorServicioRemoto` (`servicio`, `tipo`, `codigo`, `estadoHttp`).

## 1.4 Permisos

| Ruta | Acceso |
|---|---|
| `/salud`, `/salud/liveness`, `/salud/readiness`, `/openapi.json`, `/docs` | Sin token |
| `/api/ia/v1/**` | Token válido con audiencia `servicio-ia`; el rol lo define cada spec según la tabla de la constitución §9 |

## 1.5 Errores de esta funcionalidad

| HTTP | Código | Mensaje |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | "Los datos enviados no son válidos." |
| 401 | `NO_AUTENTICADO` | "Debe iniciar sesión para continuar." |
| 403 | `SIN_PERMISO` | "No tiene permiso para realizar esta operación." |
| 404 | `RECURSO_NO_ENCONTRADO` | "El recurso solicitado no existe." |
| 405 | `METODO_NO_PERMITIDO` | "El método no está permitido para este recurso." |
| 500 | `ERROR_INTERNO` | "Ocurrió un error inesperado." |
| 503 | `AUTENTICACION_NO_DISPONIBLE` | "No se pudo verificar la sesión. Intente nuevamente en unos minutos." |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | "No se pudieron obtener los datos necesarios. Intente nuevamente en unos minutos." |

Los mensajes de `401`, `404` y `503` de autenticación son iguales a los del gateway.

## 1.6 Criterios de éxito

- **CE-BASE-01:** los escenarios de las historias 1 a 4 pasan como tests automáticos, sin Keycloak, gateway ni red.
- **CE-BASE-02:** Ruff (lint y formato) y mypy sin errores; cobertura ≥ 80 % según README D-13.
- **CE-BASE-03:** `docker compose --profile ia up -d servicio-ia` deja el servicio sano (`healthcheck` en verde) y `/salud` responde `UP`.
- **CE-BASE-04 (manual, de punta a punta):** con los perfiles `backend` e `ia`:
  - el cliente de la Historia 4 obtiene el token de `servicio-ia` y `GET /api/gestion/v1/campanias/historicos?tamanio=1` a través del gateway responde `200`;
  - un token de `gerencia.prueba` en `GET {gateway}/api/ia/v1/inexistente` llega a este servicio y recibe `404 RECURSO_NO_ENCONTRADO` (enrutamiento correcto);
  - un token del client `servicio-operaciones` (sin `servicio-ia` en `aud`) en una ruta protegida recibe `401` (se verifica con la ruta de prueba, levantada solo para esta verificación).
- **CE-BASE-05:** el pipeline `.github/workflows/servicio-ia.yml` corre en verde.

## 1.7 Supuestos

- El realm ya agrega `servicio-ia` a `aud` en los tokens de usuarios y de las cuentas `graphql-server` y `n8n` (`specs/spec-keycloak-realm.md`).
- El emisor de los tokens es `http://localhost:8180/realms/agro` (lo que ve el navegador) y no es alcanzable desde el contenedor; por eso las claves se descargan de `KEYCLOAK_JWKS_URI` por la red interna y el emisor solo se compara (igual que los otros tres servicios).
- La consulta de históricos de `servicio-gestion` existe y responde con el rol `lectura_gestion` (`servicio-gestion/specs/spec-consultas-integracion.md`).

## 1.8 Aclaraciones

- **AC-01 — ¿Por qué readiness no consulta a los demás microservicios?** Si `servicio-gestion` cae, la clasificación de imágenes y la descarga de modelos siguen funcionando. Marcar este servicio como no listo cortaría también eso (RNF-08).
- **AC-02 — ¿Por qué el cliente no reintenta?** Las consultas son lecturas, pero quien las usa (un agente, un entrenamiento, un trabajo) ya tiene sus propios límites de tiempo y su manejo de error. Reintentar aquí multiplicaría la espera. La única repetición es tras un `401`, porque se resuelve con un token nuevo.
- **AC-03 — ¿Por qué la verificación de `aud` aquí y no en el gateway?** El gateway la delega a cada servicio (`api-gateway/specs/spec-enrutamiento.md`, 1.7).

## 1.9 Fuera de alcance

- Firestore, Cloud Storage y RabbitMQ (`spec-trabajos.md` en adelante).
- Clientes específicos de cada microservicio y sus `Protocol` (los define la spec que los usa, con el contrato real).
- Cualquier modelo, agente o reporte.
- CORS: lo resuelve el gateway.

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución, sin dependencias fuera del stack de la constitución §2.

**Documentos que debe tener a mano quien implemente:** la constitución (`servicios/servicio-ia/Constitucion.md`), `specs/README.md` y este archivo.

## 2.1 Proyecto y dependencias

`pyproject.toml` con `setuptools`, paquete `app`, `requires-python = ">=3.12,<3.13"` (README D-01).

| Dependencia | Para qué |
|---|---|
| `fastapi`, `uvicorn[standard]` | API HTTP (constitución §2) |
| `pydantic` v2, `pydantic-settings` | Esquemas y lectura de variables de entorno con validación al arrancar (README D-11) |
| `httpx` | Cliente HTTP asíncrono hacia Keycloak y el gateway; también lo usa el `TestClient` |
| `pyjwt[crypto]` | Validación del JWT con claves RSA del JWKS |
| Dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy` | Tests, cobertura, lint, formato y tipos (constitución §2 y §8) |

Las versiones se fijan con `~=` en la última estable al crear el proyecto. No se agregan dependencias de ML, agentes, voz, reportes ni nube (README D-02).

Configuración de herramientas en `pyproject.toml`:

- Ruff: `line-length = 100`, `target-version = "py312"`, reglas `E`, `F`, `I`, `UP`, `B`, `SIM`, `ASYNC`.
- mypy: `strict = true` sobre `app`, con el plugin de Pydantic.
- pytest: `asyncio_mode = "auto"`, `testpaths = ["tests"]`.
- coverage: `source = ["app"]`, `omit = ["app/integracion/*", "app/ml/*"]`, `fail_under = 80` (README D-13).

## 2.2 Estructura que crea esta spec

```text
servicio-ia/
├── app/
│   ├── main.py             # crear_app() y app = crear_app()
│   ├── config.py           # Configuracion (pydantic-settings)
│   ├── comun/
│   │   ├── esquemas.py     # ModeloBase, DecimalTexto, FechaHoraUtc
│   │   ├── errores.py      # ErrorAplicacion, RespuestaError, DetalleError, manejadores
│   │   ├── correlacion.py  # contexto y middleware ASGI de X-Correlation-Id + log de acceso
│   │   ├── logs.py         # FormateadorJson y configurar_logs()
│   │   ├── seguridad.py    # ProveedorClavesJwks, UsuarioAutenticado, usuario_actual, requerir_roles
│   │   └── salud.py        # RegistroSalud y router /salud
│   └── integracion/
│       ├── token_servicio.py  # TokenCuentaServicio
│       └── gateway.py         # ClienteGateway, ErrorServicioRemoto, TipoErrorRemoto
├── tests/
│   ├── conftest.py         # configuración de prueba, claves RSA, emisor de tokens, app de prueba
│   ├── unit/
│   │   ├── comun/
│   │   └── integracion/
│   └── integration/
│       └── comun/
├── Dockerfile
└── pyproject.toml
```

Las carpetas de los módulos de capacidad se crean en la spec que les da contenido (constitución §12).

## 2.3 Configuración (`app/config.py`)

`Configuracion(BaseSettings)`, sin prefijo, leída una vez en `crear_app()`:

| Variable | Obligatoria | Uso |
|---|---|---|
| `KEYCLOAK_ISSUER` | Sí | Comparación con `iss` |
| `KEYCLOAK_JWKS_URI` | Sí | Descarga de claves |
| `KEYCLOAK_AUDIENCE` | Sí | Comparación con `aud` (`servicio-ia`) |
| `KEYCLOAK_TOKEN_URL` | Sí | Token de cuenta de servicio |
| `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET` | Sí | Client credentials (`SecretStr`, nunca se registra) |
| `API_GATEWAY_URL` | Sí | Base de las consultas a otros servicios |
| `GATEWAY_TIEMPO_LIMITE_SEGUNDOS` | No (5) | Tiempo límite por defecto de cada consulta |
| `NIVEL_LOG` | No (`INFO`) | Nivel de los logs |

Las variables de Firestore, GCS, RabbitMQ, Ollama y Whisper que ya están en `docker-compose.yml` se declaran en la spec que las usa. Una variable obligatoria vacía cuenta como faltante. Si la validación falla, `main.py` escribe un log `ERROR` con los nombres de las variables (sin valores) y termina con código distinto de cero.

## 2.4 Esquemas comunes (`comun/esquemas.py`)

- `ModeloBase(BaseModel)`: `alias_generator=to_camel`, `populate_by_name=True`, `serialize_by_alias` en las respuestas (FastAPI usa `response_model_by_alias`, que ya es el valor por defecto).
- `ModeloEntrada(ModeloBase)`: además `extra="forbid"`.
- `DecimalTexto`: `Annotated[Decimal, BeforeValidator(...), PlainSerializer(str, return_type=str)]`. El validador exige `str` que coincida con `^-?\d{1,15}(\.\d{1,6})?$` y lo convierte a `Decimal`; un `int`, `float` o `bool` falla con el mensaje "Debe enviarse como texto decimal, por ejemplo \"820.50\"." La escala la fija cada esquema que lo use.
- `FechaHoraUtc`: `datetime` con zona; al serializar se convierte a UTC con sufijo `Z`. Una fecha con hora sin zona en la entrada falla.
- Fechas sin hora: `date` de Pydantic (`AAAA-MM-DD`).

## 2.5 Errores (`comun/errores.py`)

- `DetalleError(ModeloBase)`: `campo`, `mensaje`. `RespuestaError(ModeloBase)`: `codigo`, `mensaje`, `detalles: list[DetalleError]`, `id_correlacion`.
- `ErrorAplicacion(Exception)`: `estado_http`, `codigo`, `mensaje`, `detalles`. Los módulos lanzan esta excepción (o subclases) con sus códigos; no conocen FastAPI.
- `registrar_manejadores(app)`:

  | Origen | HTTP | Código |
  |---|---|---|
  | `RequestValidationError` (incluye JSON mal formado) | 400 | `DATOS_INVALIDOS`, un detalle por error; `campo` = `loc` sin el primer elemento (`body`, `query`, `path`), unido con `.`, en camelCase |
  | `ErrorAplicacion` | El suyo | El suyo |
  | `ErrorServicioRemoto` de tipo `NO_DISPONIBLE` | 503 | `DEPENDENCIA_NO_DISPONIBLE` |
  | `ErrorServicioRemoto` de otro tipo | 500 | `ERROR_INTERNO` |
  | `StarletteHTTPException` 404 | 404 | `RECURSO_NO_ENCONTRADO` |
  | `StarletteHTTPException` 405 | 405 | `METODO_NO_PERMITIDO` |
  | Cualquier otra `Exception` | 500 | `ERROR_INTERNO`, sin detalles; `logger.exception` con el `idCorrelacion` |

- `respuestas_error(*codigos_http)`: genera el diccionario `responses=` de FastAPI con `RespuestaError` para documentar cada ruta (README D-14). Toda ruta del prefijo incluye al menos 400, 401, 403 y 500.

## 2.6 Correlación, logs y log de acceso

- **`comun/logs.py`:** `FormateadorJson(logging.Formatter)` escribe un objeto JSON por línea con `fecha` (ISO UTC con `Z`), `nivel`, `logger`, `mensaje`, `idCorrelacion` (del contexto, o `null`) y los campos de `extra`; si hay excepción, `excepcion` con la traza. `configurar_logs(nivel)` instala un único `StreamHandler` en la salida estándar sobre el logger raíz y deja los de `uvicorn` sin handlers propios (propagan al raíz).
- **`comun/correlacion.py`:**
  - `id_correlacion_actual: ContextVar[str | None]`.
  - `MiddlewareCorrelacion`: middleware ASGI puro (no `BaseHTTPMiddleware`, para no romper el contexto ni el streaming). Lee y valida `X-Correlation-Id` (`[A-Za-z0-9-]{1,64}`), si no genera `uuid4`, lo pone en el contexto y en el header de la respuesta (en `http.response.start`), mide la duración y al terminar escribe el log de acceso `INFO` "solicitud atendida" con `metodo`, `ruta` (sin query), `estado`, `duracionMs` y `sub` (lo deja `usuario_actual` en `scope["state"]`).
  - Es el middleware más externo, así los errores de seguridad y los 500 ya tienen el id.
- uvicorn se lanza con `--no-access-log` (README D-10).

## 2.7 Seguridad (`comun/seguridad.py`)

- **`ProveedorClavesJwks`:** descarga el JWKS de `KEYCLOAK_JWKS_URI` con el `httpx.AsyncClient` compartido (tiempo límite 3 s) y guarda las claves por `kid` durante 10 minutos. Ante un `kid` desconocido descarga una vez más, como máximo una vez cada 30 s. Si no puede descargar y no tiene claves en caché, lanza `ErrorAplicacion(503, AUTENTICACION_NO_DISPONIBLE)`; si tiene claves vencidas, sigue usándolas y registra una advertencia.
- **`UsuarioAutenticado`** (`dataclass` congelada): `id` (`sub`), `nombre` (`name`, o `preferred_username` si falta, o `azp` en cuentas de servicio), `roles: frozenset[str]` de `realm_access.roles`.
- **`usuario_actual`** (dependencia de FastAPI): toma `Authorization: Bearer` con `HTTPBearer(auto_error=False)`; valida con `jwt.decode(token, clave, algorithms=["RS256"], audience=KEYCLOAK_AUDIENCE, issuer=KEYCLOAK_ISSUER, options={"require": ["exp", "iss", "aud", "sub"]})`. Cualquier `jwt.PyJWTError`, `kid` ausente o esquema distinto de `Bearer` → `401 NO_AUTENTICADO`. Guarda `sub` en `request.state` para el log de acceso.
- **`requerir_roles(*roles)`:** fábrica de dependencias que usa `usuario_actual` y responde `403 SIN_PERMISO` si la intersección es vacía. Las rutas la declaran así: `usuario: UsuarioAutenticado = Depends(requerir_roles("gerencia"))`.
- El router del prefijo (`APIRouter(prefix="/api/ia/v1", dependencies=[Depends(usuario_actual)])`) garantiza el token en toda ruta, aunque una ruta olvide pedir rol. Las specs siguientes cuelgan sus routers de él.
- Los tests generan un par RSA al inicio de la sesión, reemplazan `ProveedorClavesJwks` por uno con esa clave (`app.dependency_overrides`) y firman sus tokens con PyJWT: se prueban firma, `iss`, `aud`, `exp` y roles sin Keycloak.

## 2.8 Salud (`comun/salud.py`)

- `RegistroSalud` (uno por aplicación, en `app.state`): `registrar(nombre, comprobar: Callable[[], Awaitable[None]], critica: bool)`. Cada comprobación tiene 2 s de tiempo límite; una excepción o el tiempo agotado la marcan `DOWN`.
- Rutas sin prefijo y sin token:
  - `GET /salud/liveness` → `200 { "estado": "UP" }`, sin comprobaciones.
  - `GET /salud/readiness` y `GET /salud` → `{ "estado", "componentes": { nombre: "UP"|"DOWN" }, "informativos": { nombre: "UP"|"DOWN" } }`. `200` si todas las críticas están `UP`; si no, `503` con `estado = DOWN`.
- Esta spec no registra comprobaciones: `spec-trabajos.md` agrega Firestore y RabbitMQ, `spec-prediccion.md` y `spec-vision.md` los modelos cargados y `spec-agentes.md` Ollama como informativa.

## 2.9 Consulta a otros microservicios (`integracion/`)

- **`TokenCuentaServicio`:** `async obtener() -> str` y `invalidar()`. Pide el token con `grant_type=client_credentials` a `KEYCLOAK_TOKEN_URL`, lo guarda con su vencimiento (`expires_in`) y lo renueva si faltan menos de 30 s. Un `asyncio.Lock` evita pedir varios tokens a la vez. Si Keycloak falla, lanza `ErrorServicioRemoto(servicio="keycloak", tipo=NO_DISPONIBLE)`.
- **`ClienteGateway`:** `async obtener(ruta: str, parametros: Mapping[str, str] | None = None, tiempo_limite: float | None = None) -> Any`.
  - `ruta` empieza con `/api/<servicio>/v1/`; el nombre del servicio sale de ahí para el error y el log.
  - Envía `Authorization`, `Accept: application/json` y `X-Correlation-Id` del contexto.
  - Clasifica la respuesta según la Historia 4 en `TipoErrorRemoto` (`NO_DISPONIBLE`, `NO_ENCONTRADO`, `RECHAZADO`) y lanza `ErrorServicioRemoto(servicio, tipo, codigo, estado_http)`; `codigo` es el `codigo` del cuerpo de error si se puede leer.
  - Registra cada consulta en `DEBUG` (servicio, ruta, estado, duración) y cada fallo en `WARNING` (`NO_DISPONIBLE`) o `ERROR` (`RECHAZADO`, `401` repetido).
  - No tiene métodos de escritura (RN-14).
- Ambos usan un único `httpx.AsyncClient` creado en el `lifespan` de la aplicación (con `connect` de 2 s) y cerrado al terminar. `crear_app()` los guarda en `app.state` y la dependencia `cliente_gateway()` los entrega a las rutas; las specs siguientes los envuelven en sus `Protocol` (`DatosAgricolas`, etc.).

## 2.10 Aplicación (`app/main.py`)

`crear_app(configuracion: Configuracion | None = None) -> FastAPI`:

1. Lee la configuración (o usa la recibida en los tests) y llama a `configurar_logs`.
2. Crea `FastAPI(title="servicio-ia", version=..., lifespan=...)` con `openapi_url="/openapi.json"` y `docs_url="/docs"`.
3. Registra `MiddlewareCorrelacion`, los manejadores de errores, el router de salud y el router del prefijo.
4. En el `lifespan`: crea el `httpx.AsyncClient`, `ProveedorClavesJwks`, `TokenCuentaServicio`, `ClienteGateway` y `RegistroSalud`.

`app = crear_app()` al final del módulo, para uvicorn.

## 2.11 Empaquetado, entorno local y pipeline

- **`Dockerfile`** del servicio (imagen de Cloud Run): `python:3.12-slim`; copia `pyproject.toml` y `app/`; `pip install --no-cache-dir .`; usuario sin privilegios; `CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]` (Cloud Run define `PORT`). Las librerías del sistema que necesitan OpenCV y WeasyPrint se agregan en las specs que las usan.
- **`docker-compose.yml`** (`servicio-ia`):
  - comando: `pip install -q -e ".[dev]" && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --no-access-log`;
  - `healthcheck` sin `curl` (la imagen no lo trae): `python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/salud/liveness').status == 200 else 1)"`, con `start_period` de 120 s por la primera instalación;
  - sin otros cambios: las variables de 2.3 ya están.
- **`.github/workflows/servicio-ia.yml`** (en la raíz, filtrado por `servicios/servicio-ia/**` y por el propio archivo): `actions/setup-python` con 3.12 y caché de pip; `pip install -e ".[dev]"`; `ruff check .`; `ruff format --check .`; `mypy app`; `pytest --cov --cov-report=term-missing`; `docker build`. Sin contenedores de servicio en esta spec.

## 2.12 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/unit/comun/test_esquemas.py` | `DecimalTexto` acepta texto y rechaza número, `bool` y formato inválido; serializa como texto; `FechaHoraUtc` sale con `Z`; camelCase en entrada y salida; `extra="forbid"` |
| Unitario | `tests/unit/comun/test_logs.py` | Una línea JSON por registro, con `idCorrelacion` del contexto y la traza en `excepcion` |
| Unitario | `tests/unit/test_config.py` | Falta de una variable obligatoria (o vacía) → error con su nombre y sin valores |
| Unitario | `tests/unit/comun/test_seguridad_jwks.py` | Caché de 10 min, nueva descarga por `kid` desconocido limitada a una cada 30 s, claves vencidas usadas si Keycloak cae, `503` sin claves (Historia 2, escenarios 5 y 6) |
| Unitario | `tests/unit/integracion/test_token_servicio.py` | Caché, renovación a menos de 30 s, un solo pedido con consultas simultáneas, Keycloak caído (Historia 4, escenarios 1 y 2; casos borde) |
| Unitario | `tests/unit/integracion/test_cliente_gateway.py` | Headers enviados y cada clasificación de la Historia 4 (escenarios 3 a 6 y 8), con `httpx.MockTransport` |
| Integración | `tests/integration/comun/test_salud.py` | Historia 1, con comprobaciones registradas en el test |
| Integración | `tests/integration/comun/test_seguridad.py` | Historia 2, escenarios 1 a 4, con una ruta de prueba protegida por `gerencia` |
| Integración | `tests/integration/comun/test_errores.py` | Historia 3, escenarios 1 a 3, y escenario 7 de la Historia 4, con rutas de prueba |
| Integración | `tests/integration/comun/test_correlacion.py` | Historia 3, escenarios 4 a 6 (con `caplog`) |
| Integración | `tests/integration/test_openapi.py` | `/openapi.json` y `/docs` sin token; toda ruta del prefijo documenta 400, 401, 403 y 500 con `RespuestaError`. En esta spec recorre las rutas de prueba; desde la siguiente, las reales |

Las rutas de prueba se registran solo en `tests/conftest.py`, sobre una aplicación creada con `crear_app(configuracion_de_prueba)`; no existen en el código de `app`.

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

- [ ] **T01** — Crear `pyproject.toml` con las dependencias y la configuración de herramientas de 2.1, y la estructura de 2.2. *Hecho cuando:* `pip install -e ".[dev]"`, `ruff check .` y `mypy app` funcionan en la imagen de desarrollo.
- [ ] **T02** — Implementar `config.py` y `comun/esquemas.py`. *Hecho cuando:* pasan `test_config.py` y `test_esquemas.py`.
- [ ] **T03** [P] — Implementar `comun/logs.py` y `comun/correlacion.py`. *Hecho cuando:* pasa `test_logs.py`.
- [ ] **T04** — Implementar `comun/errores.py`, `main.py` (`crear_app`) y `tests/conftest.py` con la aplicación y las rutas de prueba. *Hecho cuando:* pasan `test_errores.py` (salvo el escenario 7 de la Historia 4) y `test_correlacion.py`.
- [ ] **T05** — Implementar `comun/salud.py`. *Hecho cuando:* pasa `test_salud.py`.
- [ ] **T06** — Implementar `comun/seguridad.py` y el emisor de tokens de prueba. *Hecho cuando:* pasan `test_seguridad_jwks.py` y `test_seguridad.py`.
- [ ] **T07** — Implementar `integracion/token_servicio.py` e `integracion/gateway.py` y su manejo en `errores.py`. *Hecho cuando:* pasan `test_token_servicio.py`, `test_cliente_gateway.py` y el escenario 7 de la Historia 4.
- [ ] **T08** — Escribir `test_openapi.py` y documentar las respuestas de error de las rutas. *Hecho cuando:* pasa, y la cobertura es ≥ 80 % (README D-13).
- [ ] **T09** [P] — Escribir el `Dockerfile`, ajustar `docker-compose.yml` (2.11) y crear `.github/workflows/servicio-ia.yml`. *Hecho cuando:* se cumplen CE-BASE-03 y CE-BASE-05, y la imagen de producción responde `/salud/liveness`.
- [ ] **T10** — Verificación manual de punta a punta (CE-BASE-04). *Hecho cuando:* los tres puntos responden lo esperado; se anota el resultado en esta tarea.
