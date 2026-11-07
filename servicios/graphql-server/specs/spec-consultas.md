# Consultas consolidadas para React — `graphql-server`

| Campo | Valor |
|---|---|
| Servicio | `graphql-server` |
| Archivo | `specs/spec-consultas.md` |
| Estado | Spec, plan y tareas aprobados (2026-11-07) |
| Constitución | v1.0.0 |
| Trazabilidad | CU-05, CU-14, CU-15, CU-24 · RF-06, RF-18, RF-19, RF-27, RF-33 · RN-13, RN-14, RN-15, RN-16 · RNF-02, RNF-03, RNF-05, RNF-08, RNF-19, RNF-20, RNF-22 |
| Depende de | `api-gateway/specs/spec-ruta-graphql.md` (ruta `/api/graphql`). Los cuatro microservicios y el realm `agro`, ya implementados. |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servidor.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

Esta spec incluye la base del servidor (seguridad, errores, correlación, salud y cliente del gateway), porque es la única.

---

# 1. Spec

## Contexto

El microfrontend React (`/analisis`) es la interfaz de gerencia: consulta indicadores de rendimiento, costos y producción, compara campañas, revisa el estado del inventario y los resultados de los modelos de IA (§1.7.5 y §1.9 del documento de requisitos). El proceso 7 pide que React obtenga esos datos con Apollo Client desde un servidor GraphQL "que combina datos de Spring Boot, NestJS, Laravel y FastAPI en una sola respuesta" (RF-27).

Todo lo que el servidor necesita ya existe en los microservicios, con permisos para su cuenta de servicio:

| Servicio | Endpoints que usa | Rol de la cuenta `graphql-server` |
|---|---|---|
| `servicio-gestion` | `GET /parcelas`, `/parcelas/{id}`, `/cultivos`, `/cultivos/{id}`, `/campanias`, `/campanias/{id}`, `/campanias/{id}/indicadores`, `/campanias/{id}/costos`, `/campanias/{id}/produccion`, `/campanias/historicos` | `lectura_gestion` |
| `servicio-inventario` | `GET /estado-inventario`, `/insumos`, `/insumos/{id}` | `lectura_inventario` |
| `servicio-operaciones` | `GET /labores`, `/incidencias` | `lectura_operaciones` |
| `servicio-ia` | `GET /predicciones`, `/analisis`, `/analisis/{id}` | `lectura_ia` |

Lo que React hace por REST y **no** pasa por GraphQL (constitución §1): pedir predicciones y análisis nuevos (`POST /predicciones`, `POST /analisis`), consultar al agente, pedir reportes por texto o voz, descargarlos y consultar trabajos.

## 1.1 Escenarios de usuario y pruebas

### Historia 1 — Ver campañas con sus indicadores en una sola consulta (Prioridad: P1)

Como gerencia, quiero ver las campañas con su parcela, cultivo, indicadores y costos por categoría en una sola consulta, para armar el tablero de análisis (CU-05, RF-06, RF-27).

**Por qué esta prioridad:** es la razón de ser del servidor (RF-27) y la vista principal de React.

**Prueba independiente:** con el gateway simulado devolviendo respuestas fijas de gestión, se ejecuta la consulta del tablero y se comparan los valores con los de REST.

**Escenarios de aceptación:**

1. **Dado** tres campañas en distintos estados, **cuando** gerencia consulta `campanias` con `parcela`, `cultivo` e `indicadores`, **entonces** recibe las tres con exactamente los valores que devuelve `servicio-gestion` (mismos textos decimales, mismas fechas, mismo orden).
2. **Dado** una campaña sin producción, **entonces** `indicadores.rendimientoPorHectarea` es `null` y `motivosNoDisponible` contiene `SIN_PRODUCCION`, tal como lo informa gestión (RN-03): el servidor no calcula ni completa nada.
3. **Dado** dos campañas de la misma parcela, **entonces** la parcela se consulta una sola vez en esa solicitud.
4. **Dado** una campaña, **cuando** se pide `costos`, **entonces** recibe `costoTotal` y un subtotal por cada categoría (`INSUMO`, `MANO_DE_OBRA`, `MAQUINARIA`, `OTRO`) con los valores de gestión.
5. **Dado** `campania(id)` con un ID inexistente, **entonces** recibe `null` sin error.

### Historia 2 — Comparar campañas finalizadas (Prioridad: P1)

Como gerencia, quiero las campañas finalizadas con su producción, costos por categoría e indicadores, para compararlas (§1.7.5 "comparar campañas").

**Escenarios de aceptación:**

1. **Dado** campañas finalizadas, **cuando** se consulta `campaniasFinalizadas` con filtro por cultivo, **entonces** recibe los registros de `GET /campanias/historicos` de gestión, en su orden y con su paginación.
2. **Dado** una campaña finalizada sin costos, **entonces** sus indicadores son `null` con `SIN_COSTOS`.

### Historia 3 — Revisar el estado del inventario (Prioridad: P1)

Como gerencia, quiero ver los insumos frente a su nivel mínimo, con el resumen de stock bajo, junto con las campañas (CU-24, RF-33).

**Escenarios de aceptación:**

1. **Dado** insumos en stock bajo, **cuando** se consulta `estadoInventario(soloStockBajo: true)`, **entonces** recibe los ítems y el `resumen` tal como los devuelve inventario.
2. **Dado** una consulta con `campanias` y `estadoInventario`, **entonces** las dos partes llegan en la misma respuesta y las llamadas a gestión e inventario se hacen en paralelo.

### Historia 4 — Ver los resultados de los modelos de IA (Prioridad: P2)

Como gerencia, quiero ver las predicciones de una campaña junto con su rendimiento real, y el último análisis de patrones con las campañas atípicas (CU-14, CU-15, procesos 9 y 10).

**Escenarios de aceptación:**

1. **Dado** una campaña finalizada con predicciones, **cuando** se consulta `campania(id) { indicadores predicciones }`, **entonces** recibe las predicciones de IA (la más reciente primero, con `rendimientoEstimado`, `intervalo` y `rendimientoReal`) y los indicadores reales de gestión en la misma respuesta.
2. **Dado** un análisis, **cuando** se consulta `analisisPorId` con `anomalias { campania { nombre } }`, **entonces** cada anomalía trae su campaña de gestión.
3. **Dado** cualquier resultado de IA, **entonces** incluye `orientativo: true` y el `aviso` de IA (RN-13).
4. **Dado** que todavía no hay ningún análisis, **entonces** `analisis` devuelve una página vacía, no un error.

### Historia 5 — Ver las operaciones de una campaña (Prioridad: P2)

Como gerencia o administrador, quiero ver las labores e incidencias de una campaña con los nombres de los insumos usados, para seguir lo que pasa en el campo.

**Escenarios de aceptación:**

1. **Dado** una campaña con labores, **cuando** se consulta `campania(id) { labores { items { estado insumos { cantidad insumo { nombre unidad } } } } }`, **entonces** recibe las labores de operaciones con los insumos de inventario.
2. **Dado** más labores que el `limite`, **entonces** recibe `siguienteCursor` y, con él, la página siguiente (paginación por cursor de operaciones).
3. **Dado** una incidencia con foto, **entonces** recibe la URL prefirmada tal como la entrega operaciones (vence a los 10 minutos).
4. **Dado** `labores` sin `idCampania`, `idResponsable` ni `estado`, **entonces** recibe el error `DATOS_INVALIDOS` que devuelve operaciones.

### Historia 6 — Ver solo lo que mi rol permite (Prioridad: P1)

Como responsable del sistema, quiero que GraphQL no entregue datos que el usuario no podría leer por REST, aunque la cuenta de servicio sí pueda (RN-15, RN-16).

**Escenarios de aceptación:**

1. **Dado** una solicitud sin token o con un token vencido, de otro emisor o firmado con otra clave, **entonces** responde `401 NO_AUTENTICADO` y no llama a ningún servicio.
2. **Dado** un token válido cuya `aud` no incluye `graphql-server`, **entonces** `401 NO_AUTENTICADO`.
3. **Dado** `tecnico.prueba`, **entonces** `403 SIN_PERMISO` y no llama a ningún servicio.
4. **Dado** `admin.prueba`, **cuando** consulta `campania(id) { indicadores predicciones }`, **entonces** recibe `indicadores`, y `predicciones` queda en `null` con el error `SIN_PERMISO` (IA no permite a `administrador` leer predicciones); la llamada a IA no se hace.
5. **Dado** `multirol.prueba` (`administrador` y `gerencia`), **entonces** recibe todo.
6. **Dado** cualquier rol, **entonces** el esquema no tiene `Mutation`: una operación `mutation` se rechaza en la validación.

### Historia 7 — Seguir respondiendo aunque un servicio caiga (Prioridad: P1)

Como gerencia, quiero ver lo que sí está disponible cuando un servicio no responde, en vez de una pantalla en blanco (RNF-08).

**Escenarios de aceptación:**

1. **Dado** que inventario responde `503`, **cuando** se consulta `campanias` y `estadoInventario`, **entonces** `campanias` llega completo y `estadoInventario` es `null` con el error `DEPENDENCIA_NO_DISPONIBLE`.
2. **Dado** que una llamada tarda más que el tiempo límite, **entonces** ese campo responde `DEPENDENCIA_NO_DISPONIBLE` en cuanto se cumple el tiempo.
3. **Dado** que la cuenta de servicio no puede obtener su token (Keycloak caído), **entonces** cada campo que consulta un servicio responde `DEPENDENCIA_NO_DISPONIBLE`.
4. **Dado** que ningún microservicio está levantado, **entonces** `/salud/readiness` sigue respondiendo `UP`.
5. **Dado** una consulta que necesita más llamadas que el máximo, **entonces** las llamadas que exceden el máximo no se hacen y sus campos responden `CONSULTA_DEMASIADO_COMPLEJA`.
6. **Dado** una consulta de tres niveles anidados (`campania(id) { labores { items { insumos { insumo { nombre } } } } }`) con gestión tardando 3 s, operaciones 3 s e inventario sin responder, **entonces** la respuesta llega a los 4,5 s (el plazo total), con la campaña completa y `labores` en `null` con `DEPENDENCIA_NO_DISPONIBLE`; la llamada a operaciones abierta se corta y la de inventario no llega a hacerse. Sin el plazo serían 3 + 3 + 4 = 10 s: el gateway cortaría con `504` y se perdería la respuesta parcial.
7. **Dado** que las claves de Keycloak no están en la caché del servidor y el JWKS tarda 1 s en responder, y un servicio acepta la conexión y nunca responde, **entonces** la respuesta llega antes de los 4,7 s contados desde que el servidor recibió la solicitud: el plazo empieza al recibirla, no después de validar el token.

### Historia 8 — Seguir una consulta de punta a punta (Prioridad: P2)

Como desarrollador, quiero el mismo identificador de correlación en el gateway, en GraphQL y en cada servicio consultado (RNF-22).

**Escenarios de aceptación:**

1. **Dado** una solicitud con `X-Correlation-Id: abc-123`, **entonces** cada llamada a los servicios lleva `abc-123`, la respuesta lo devuelve y cada error de campo lo incluye en `extensions.idCorrelacion`.
2. **Dado** una solicitud sin el header o con uno inválido, **entonces** se genera un UUID y se usa igual.
3. **Dado** cualquier consulta, **entonces** se escribe un log JSON con `idCorrelacion`, `operacion`, `estado`, `duracionMs`, `cantidadLlamadas`, `cantidadErrores` y `sub`, sin el token, el texto de la consulta ni sus variables.

### Casos borde

- **`tamanio` o `limite` mayor a 50:** error `DATOS_INVALIDOS` sin llamar al servicio. Es menor que el máximo de los servicios (100) para acotar las llamadas anidadas de una página (RNF-05).
- **Entidad referenciada que ya no existe** (por ejemplo, el insumo de una labor): el campo anidado es `null` sin error, igual que `campania(id)`.
- **El token de la cuenta de servicio vence entre dos llamadas:** el servicio responde `401`; se renueva el token y se repite esa llamada una vez, si el plazo de la consulta todavía lo permite. Si vuelve a fallar o ya no cabe, `DEPENDENCIA_NO_DISPONIBLE`.
- **Varias consultas esperan el mismo token de servicio y el plazo de una vence:** solo esa consulta deja de esperar; la obtención del token sigue para las demás.
- **Keycloak falla o no responde y el servidor todavía no tiene las claves para validar el token del usuario:** `503 AUTENTICACION_NO_DISPONIBLE`, no `401`, como en el gateway. La descarga de las claves se corta a los 1,5 s, así que la respuesta no espera sin tope.
- **Origen de Apollo Sandbox o Studio** (`https://sandbox.embed.apollographql.com`, `https://studio.apollographql.com`) fuera de producción: la verificación previa (`OPTIONS`, sin token) responde `204` con los headers de CORS; las consultas reales siguen exigiendo token. Cualquier otro origen, o cualquier origen en producción, no recibe headers de CORS.
- **Consulta mal formada o con un campo inexistente:** error de validación de GraphQL con `extensions.codigo = DATOS_INVALIDOS`.
- **Un servicio responde `403` a la cuenta de servicio:** es un error del realm. Se registra en el log y el campo responde `ERROR_INTERNO`.
- **Un servicio cambia un campo de su respuesta:** el test de contrato de ese servicio falla (T02); el esquema se ajusta en una spec.

## 1.2 Requisitos

### Requisitos funcionales

- **RQ-GQL-01:** exponer en `/api/graphql` el esquema de 2.3, solo con consultas.
- **RQ-GQL-02:** validar firma, `iss`, `aud` (`graphql-server`) y `exp` del token del usuario y exigir `administrador` o `gerencia`.
- **RQ-GQL-03:** aplicar la tabla de permisos de 1.3 por campo, sin llamar al servicio cuando el rol no alcanza.
- **RQ-GQL-04:** obtener cada dato del servicio dueño, a través del gateway, con la cuenta de servicio, y entregarlo sin cambiar ningún valor.
- **RQ-GQL-05:** dentro de una solicitud, consultar una sola vez cada entidad pedida por ID y hacer en paralelo las llamadas independientes.
- **RQ-GQL-06:** cada llamada con tiempo límite y un solo intento (salvo la renovación del token ante `401`); plazo total por consulta, menor que la meta de RNF-05 y que el tiempo límite del gateway; máximo de llamadas por consulta.
- **RQ-GQL-10:** no emitir headers de CORS, salvo fuera de producción para los orígenes de Apollo Sandbox y Studio.
- **RQ-GQL-07:** traducir los errores de los servicios según la constitución §7 y entregar el resto de la respuesta.
- **RQ-GQL-08:** conservar o generar `X-Correlation-Id`, propagarlo y escribir el log de la historia 8.
- **RQ-GQL-09:** exponer `/salud`, `/salud/liveness` y `/salud/readiness` sin token, sin depender de otros servicios.

### Entidades clave

El servidor no tiene entidades propias. Sus tipos son proyecciones de los contratos de los servicios dueños (2.3).

## 1.3 Permisos

Regla (constitución §5): un campo solo se entrega a los roles de usuario que el servicio dueño autoriza para esos datos.

| Campo de GraphQL | Roles de usuario | Endpoint (a través del gateway) | Permiso del servicio dueño para usuarios |
|---|---|---|---|
| `parcelas`, `cultivos`, `Campania.parcela`, `Campania.cultivo`, `Labor.parcela`, `Incidencia.parcela` | `administrador`, `gerencia` | `GET /api/gestion/v1/parcelas[/{id}]`, `/cultivos[/{id}]` | `spec-parcelas.md`, `spec-cultivos.md` |
| `campanias`, `campania`, `Labor.campania`, `Incidencia.campania`, `Anomalia.campania` | `administrador`, `gerencia` | `GET /api/gestion/v1/campanias[/{id}]` | `spec-campanias.md` |
| `Campania.indicadores` | `administrador`, `gerencia` | `GET .../campanias/{id}/indicadores` | `spec-indicadores.md` |
| `Campania.costos` | `administrador`, `gerencia` | `GET .../campanias/{id}/costos?tamanio=1` | `spec-costos-manuales.md` |
| `Campania.produccion` | `administrador`, `gerencia` | `GET .../campanias/{id}/produccion` | `spec-produccion.md` |
| `campaniasFinalizadas` | `administrador`, `gerencia` | `GET .../campanias/historicos` | Endpoint de integración (`lectura_gestion`); cada uno de sus datos lo leen ambos roles en los endpoints anteriores (1.7) |
| `estadoInventario` | `administrador`, `gerencia` | `GET /api/inventario/v1/estado-inventario` | `spec-estado-inventario.md` |
| `insumos`, `ConsumoInsumo.insumo` | `administrador`, `gerencia` | `GET /api/inventario/v1/insumos[/{id}]` (vista completa) | `spec-insumos.md` |
| `labores`, `Campania.labores` | `administrador`, `gerencia` | `GET /api/operaciones/v1/labores` | `spec-labores.md` RQ-LAB-17 |
| `incidencias`, `Campania.incidencias` | `administrador`, `gerencia` | `GET /api/operaciones/v1/incidencias` | `spec-incidencias.md` RQ-INC-12 |
| `Campania.predicciones` | `gerencia` | `GET /api/ia/v1/predicciones?idCampania=` | `spec-prediccion.md` 1.4 |
| `analisis`, `analisisPorId` | `gerencia` | `GET /api/ia/v1/analisis[/{id}]` | `spec-prediccion.md` 1.4 |

`tecnico_campo` y las cuentas de servicio no usan este servidor (403).

## 1.4 Errores de esta funcionalidad

Errores HTTP (formato común, constitución §7):

| HTTP | `codigo` | `mensaje` |
|---|---|---|
| 401 | `NO_AUTENTICADO` | "Debe iniciar sesión para continuar." |
| 403 | `SIN_PERMISO` | "No tiene permiso para realizar esta operación." |
| 503 | `AUTENTICACION_NO_DISPONIBLE` | "No se pudo verificar la sesión. Intente nuevamente en unos minutos." |
| 500 | `ERROR_INTERNO` | "Ocurrió un error inesperado." |

Errores de campo (`extensions.codigo`):

| `codigo` | `mensaje` | Cuándo |
|---|---|---|
| `SIN_PERMISO` | "No tiene permiso para ver esta información." | 1.3 |
| `DATOS_INVALIDOS` | "La consulta tiene datos inválidos." (con los `detalles` del servicio, si los hay) | Validación de GraphQL, argumentos fuera de rango o `400` del servicio |
| `DEPENDENCIA_NO_DISPONIBLE` | "No se pudieron obtener estos datos en este momento." | `503`, `504`, tiempo límite de la llamada agotado, plazo de la consulta vencido, conexión rechazada o token de servicio no disponible |
| `CONSULTA_DEMASIADO_COMPLEJA` | "La consulta pide demasiados datos a la vez." | Se superó el máximo de llamadas |
| `ERROR_INTERNO` | "Ocurrió un error inesperado." | `403` del servicio a la cuenta de servicio o cualquier otro fallo |

## 1.5 Criterios de éxito

- **CE-GQL-01:** los escenarios de las historias 1 a 8 y los casos borde pasan como tests automáticos.
- **CE-GQL-02:** la consulta del tablero (20 campañas con `parcela`, `cultivo` e `indicadores`, más `estadoInventario` con su resumen), contra un gateway simulado que tarda 200 ms en cada respuesta, responde en menos de 1,5 s. Son unas 25 llamadas: en serie tardarían unos 5 s; en paralelo, dos rondas (el listado junto con el inventario y, después, los datos anidados), unos 0,4 s. Así se comprueba el paralelismo y queda margen para la meta de RNF-05 (5 s).
- **CE-GQL-03:** con los perfiles `backend`, `ia` y `graphql` levantados, la consulta del tablero hecha por `gerencia.prueba` a través del gateway (`POST http://localhost:8080/api/graphql`) devuelve los mismos valores que las llamadas REST equivalentes, y el mismo `idCorrelacion` aparece en los logs del gateway, de `graphql-server` y de `servicio-gestion` (prueba manual, T14).
- **CE-GQL-04:** la cobertura de líneas de `src` es ≥ 80 %.
- **CE-GQL-05:** con un servicio que acepta la conexión y nunca responde, toda consulta responde en menos de 5 s, medidos en `graphql-server` desde que recibe la solicitud, incluida la validación del token (historia 7, escenarios 6 y 7).

## 1.6 Supuestos

- La ruta `/api/graphql` del gateway (`spec-ruta-graphql.md`) valida firma, emisor y vigencia antes de reenviar; el servidor vuelve a validar el token completo, como cada microservicio.
- La garantía de responder en menos de 5 s (CE-GQL-05) es de `graphql-server`, no de punta a punta: la descarga del JWKS del gateway no tiene tiempo límite propio (`spec-enrutamiento.md`, casos borde, limitación conocida), así que con un Keycloak que no responde y las claves fuera de la caché del gateway, la solicitud puede quedar esperando antes de llegar al servidor.
- Los contratos REST de 1.1 están implementados como dicen sus specs. Antes de escribir cada cliente se revisan contra el OpenAPI real del servicio (T02).
- El realm agrega `graphql-server` a la audiencia de los tokens de `agro-web` y `agro-pruebas` (2.10).
- El volumen de datos es el de un productor pequeño o mediano (§1.2.2): decenas de campañas y cientos de insumos.

## 1.7 Aclaraciones

- **¿Por qué la cuenta de servicio y no el token del usuario?** El realm y las specs de los cuatro servicios ya definieron la cuenta `graphql-server` con roles de solo lectura (`spec-keycloak-realm.md` RQ-KC-04). Para no entregar más de lo que el usuario vería por REST, el servidor aplica la tabla de 1.3, construida a partir de los permisos de cada servicio.
- **¿Por qué `campaniasFinalizadas` se entrega a usuarios si usa un endpoint de integración?** Cada uno de sus campos (producción, costos por categoría e indicadores) lo leen `administrador` y `gerencia` en los endpoints de usuario de gestión. El endpoint de históricos solo los entrega juntos y de una vez, sin una llamada por campaña.
- **¿Por qué no hay mutaciones?** Decisión del 2026-11-06: RF-27 pide consultas consolidadas. Las operaciones de IA son asíncronas, solo las consulta quien las pidió (`spec-trabajos.md`) y exigen roles de usuario que la cuenta de servicio no tiene.
- **¿Por qué `/api/graphql` y no `/graphql`?** Con ese prefijo la ruta queda cubierta por la seguridad y el CORS que el gateway ya aplica a `/api/**`, sin código nuevo en el gateway. GraphQL no se versiona en la URL: el esquema evoluciona agregando campos.
- **¿Por qué no hay movimientos de inventario?** La cuenta de servicio no puede leerlos (`servicio-inventario`, AP-03) y ninguna pantalla de React los pide.

## 1.8 Fuera de alcance

- Mutaciones, suscripciones y operaciones de IA (constitución §1).
- Consultas persistidas, caché de respuestas y federación.
- Pantallas de React: se definen en la spec del microfrontend.

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución.

**Documentos que debe tener a mano quien implemente:** la constitución v1.0.0 (`servicios/graphql-server/Constitucion.md`), este archivo y el OpenAPI de cada servicio consultado.

## 2.1 Dependencias (`package.json`)

| Dependencia | Para qué |
|---|---|
| Node 24 LTS (imagen `node:24-alpine`, la de `docker/node`), TypeScript 5 en modo `strict` | Base |
| `@apollo/server` (versión estable vigente, fijada) y `graphql` 16 | Servidor GraphQL (Módulo 9) |
| `express` 5 y `@as-integrations/express5` | Rutas `/salud`, correlación, log de acceso y validación del token antes de Apollo |
| `jose` | Validación del JWT con JWKS (misma librería que `servicio-inventario`) |
| `dataloader` | Una sola consulta por ID dentro de una solicitud (RQ-GQL-05) |
| Desarrollo: `tsx` | `npm run dev` con recarga al guardar (comando de Docker Compose) |
| Test: `jest`, `ts-jest`, `supertest` | Tests con el gateway y Keycloak simulados |
| Calidad: `eslint`, `typescript-eslint`, `prettier` | Mismo estilo que `servicio-inventario` |

No se usa un cliente HTTP externo (el `fetch` nativo alcanza), ni generadores de tipos desde el esquema, ni librerías de límites de complejidad (lo resuelve el máximo de llamadas, 2.6).

## 2.2 Configuración (`src/config.ts`)

| Variable | Uso | Valor local (Docker Compose) |
|---|---|---|
| `PORT` | Puerto HTTP | `4000` |
| `API_GATEWAY_URL` | Base de las llamadas a los servicios | Ya definida (`http://api-gateway:8080`) |
| `KEYCLOAK_JWKS_URI`, `KEYCLOAK_ISSUER` | Validación del token del usuario | Ya definidas (`x-keycloak-env`) |
| `KEYCLOAK_AUDIENCE` | `aud` exigida | Nueva: `graphql-server` |
| `KEYCLOAK_TOKEN_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET` | Token de la cuenta de servicio | Ya definidas |
| `GRAPHQL_TIEMPO_LIMITE_LLAMADA_MS` | Tiempo límite de cada llamada | Por defecto `4000` |
| `GRAPHQL_PLAZO_CONSULTA_MS` | Plazo total de una consulta | Por defecto `4500` |
| `GRAPHQL_MAXIMO_LLAMADAS` | Máximo de llamadas por consulta | Por defecto `200` |
| `NODE_ENV` | `production` desactiva la página de Apollo Sandbox y la excepción de CORS de 2.5 | Sin definir en local |

Si falta una variable sin valor por defecto, el proceso no arranca (RNF-03). Al arrancar se valida que `GRAPHQL_PLAZO_CONSULTA_MS` sea menor que 5000 (RNF-05). Son constantes, no variables: el tamaño máximo de página (50), el tiempo límite de la descarga del JWKS (1.500 ms) y el de la obtención del token de servicio (2.000 ms).

## 2.3 Esquema (`src/esquema/esquema.graphql`)

```graphql
"Decimal exacto como texto con punto decimal, por ejemplo \"820.50\"."
scalar Decimal
"Fecha sin hora, AAAA-MM-DD."
scalar Fecha
"Fecha y hora ISO 8601 UTC."
scalar FechaHora

enum EstadoCampania { PLANIFICADA EN_CURSO FINALIZADA }
enum CategoriaCosto { INSUMO MANO_DE_OBRA MAQUINARIA OTRO }
enum MotivoIndicadorNoDisponible { SIN_PRODUCCION SIN_COSTOS }
enum CategoriaInsumo { SEMILLA FERTILIZANTE FITOSANITARIO }
enum UnidadMedida { KILOGRAMO LITRO UNIDAD }
enum EstadoLabor { PROGRAMADA PENDIENTE CONFIRMADA RECHAZADA PENDIENTE_REVISION }
enum TipoLabor { PREPARACION_SUELO SIEMBRA FERTILIZACION RIEGO CONTROL_FITOSANITARIO DESHIERBE COSECHA OTRA }
enum TipoIncidencia { PLAGA ENFERMEDAD DANIO OTRO }
enum OrigenClasificacion { DISPOSITIVO SERVIDOR }
enum Orden { ASC DESC }

type Query {
  parcelas(nombre: String, pagina: Int = 0, tamanio: Int = 20): PaginaParcelas
  cultivos(nombre: String, pagina: Int = 0, tamanio: Int = 20): PaginaCultivos
  campanias(filtro: FiltroCampanias, pagina: Int = 0, tamanio: Int = 20): PaginaCampanias
  campania(id: ID!): Campania
  campaniasFinalizadas(filtro: FiltroCampaniasFinalizadas, pagina: Int = 0, tamanio: Int = 20): PaginaCampaniasFinalizadas
  estadoInventario(categoria: CategoriaInsumo, soloStockBajo: Boolean = false, pagina: Int = 0, tamanio: Int = 20): EstadoInventario
  insumos(nombre: String, categoria: CategoriaInsumo, pagina: Int = 0, tamanio: Int = 20): PaginaInsumos
  labores(filtro: FiltroLabores!, limite: Int = 20, cursor: String): PaginaLabores
  incidencias(filtro: FiltroIncidencias!, limite: Int = 20, cursor: String): PaginaIncidencias
  analisis(pagina: Int = 0, tamanio: Int = 20): PaginaResumenAnalisis
  analisisPorId(id: ID!): Analisis
}

# --- servicio-gestion ---

type Parcela { id: ID! nombre: String! superficieHectareas: Decimal! ubicacion: String descripcion: String }
type Cultivo { id: ID! nombre: String! variedad: String unidadMedida: String! }

type Campania {
  id: ID!
  nombre: String!
  estado: EstadoCampania!
  fechaInicio: Fecha!
  fechaFin: Fecha!
  superficieHectareas: Decimal!
  fechaInicioEjecucion: FechaHora
  fechaFinalizacion: FechaHora
  parcela: Parcela
  cultivo: Cultivo
  indicadores: Indicadores
  costos: ResumenCostos
  "null si la campaña no tiene producción registrada."
  produccion: Produccion
  predicciones(pagina: Int = 0, tamanio: Int = 5): PaginaPredicciones
  labores(estado: EstadoLabor, limite: Int = 20, cursor: String): PaginaLabores
  incidencias(tipo: TipoIncidencia, limite: Int = 20, cursor: String): PaginaIncidencias
}

type Indicadores {
  estadoCampania: EstadoCampania!
  definitivo: Boolean!
  superficieHectareas: Decimal!
  produccion: Decimal
  costoTotal: Decimal
  rendimientoPorHectarea: Decimal
  costoPorHectarea: Decimal
  motivosNoDisponible: [MotivoIndicadorNoDisponible!]!
}

type MontoPorCategoria { categoria: CategoriaCosto! monto: Decimal! }
type ResumenCostos { costoTotal: Decimal! subtotalesPorCategoria: [MontoPorCategoria!]! }
type Produccion { cantidad: Decimal! unidad: String! fechaCosecha: Fecha! observaciones: String }

type CampaniaFinalizada {
  idCampania: ID!
  idParcela: ID!
  nombreParcela: String!
  superficieHectareas: Decimal!
  idCultivo: ID!
  nombreCultivo: String!
  variedad: String
  fechaInicio: Fecha!
  fechaFin: Fecha!
  fechaInicioEjecucion: FechaHora
  fechaFinalizacion: FechaHora!
  duracionDias: Int!
  produccion: Decimal!
  fechaCosecha: Fecha
  costoTotal: Decimal!
  costosPorCategoria: [MontoPorCategoria!]!
  rendimientoPorHectarea: Decimal
  costoPorHectarea: Decimal
  motivosNoDisponible: [MotivoIndicadorNoDisponible!]!
}

input FiltroCampanias { estado: EstadoCampania idParcela: ID idCultivo: ID fechaInicioDesde: Fecha fechaInicioHasta: Fecha }
input FiltroCampaniasFinalizadas { idCultivo: ID idParcela: ID fechaFinalizacionDesde: Fecha fechaFinalizacionHasta: Fecha }

type PaginaParcelas { items: [Parcela!]! pagina: Int! tamanio: Int! total: Int! }
type PaginaCultivos { items: [Cultivo!]! pagina: Int! tamanio: Int! total: Int! }
type PaginaCampanias { items: [Campania!]! pagina: Int! tamanio: Int! total: Int! }
type PaginaCampaniasFinalizadas { items: [CampaniaFinalizada!]! pagina: Int! tamanio: Int! total: Int! }

# --- servicio-inventario ---

type ResumenInventario { totalInsumos: Int! totalStockBajo: Int! }
type EstadoInsumo {
  idInsumo: ID!
  nombre: String!
  categoria: CategoriaInsumo!
  unidad: UnidadMedida!
  stock: Decimal!
  nivelMinimo: Decimal!
  stockBajo: Boolean!
  fechaUltimaAlerta: FechaHora
}
type EstadoInventario { resumen: ResumenInventario! items: [EstadoInsumo!]! pagina: Int! tamanio: Int! total: Int! }

type Insumo {
  id: ID!
  nombre: String!
  categoria: CategoriaInsumo!
  unidad: UnidadMedida!
  stock: Decimal!
  nivelMinimo: Decimal!
  costoUnitario: Decimal!
  stockBajo: Boolean!
}
type PaginaInsumos { items: [Insumo!]! pagina: Int! tamanio: Int! total: Int! }

# --- servicio-operaciones ---

type Persona { id: ID! nombre: String! }
type Motivo { codigo: String! mensaje: String! }
type ConsumoInsumo { idInsumo: ID! cantidad: Decimal! insumo: Insumo }

type Labor {
  id: ID!
  tipoLabor: TipoLabor!
  estado: EstadoLabor!
  fechaReferencia: FechaHora!
  fechaProgramada: Fecha
  fechaEjecucion: FechaHora
  responsable: Persona
  observaciones: String
  insumos: [ConsumoInsumo!]!
  motivo: Motivo
  idParcela: ID!
  idCampania: ID!
  parcela: Parcela
  campania: Campania
}

type Foto { url: String! tipoContenido: String! tamanio: Int! expiraEn: FechaHora! }
type Clasificacion { categoria: String! confianza: Decimal! versionModelo: String! origen: OrigenClasificacion! orientativa: Boolean! }

type Incidencia {
  id: ID!
  tipo: TipoIncidencia!
  descripcion: String!
  fechaObservacion: FechaHora!
  foto: Foto
  clasificacion: Clasificacion
  registradaPor: Persona
  idParcela: ID!
  idCampania: ID
  parcela: Parcela
  campania: Campania
}

input FiltroLabores { idCampania: ID idResponsable: ID estado: EstadoLabor fechaDesde: Fecha fechaHasta: Fecha orden: Orden }
input FiltroIncidencias { idParcela: ID idCampania: ID tipo: TipoIncidencia fechaDesde: Fecha fechaHasta: Fecha orden: Orden }

type PaginaLabores { items: [Labor!]! siguienteCursor: String }
type PaginaIncidencias { items: [Incidencia!]! siguienteCursor: String }

# --- servicio-ia ---

type VersionModelo { nombre: String! version: Int! }
type Intervalo { minimo: Decimal! maximo: Decimal! }

type Prediccion {
  id: ID!
  fecha: FechaHora!
  cultivo: String!
  estadoCampania: EstadoCampania!
  origenCostos: String!
  costosPorHectarea: [MontoPorCategoria!]!
  rendimientoEstimado: Decimal!
  intervalo: Intervalo!
  produccionEstimada: Decimal!
  rendimientoReal: Decimal
  unidad: String!
  advertencias: [Advertencia!]!
  versionModelo: VersionModelo!
  orientativo: Boolean!
  aviso: String!
}
type Advertencia { codigo: String! campos: [String!] }
type PaginaPredicciones { items: [Prediccion!]! pagina: Int! tamanio: Int! total: Int! }

type ResumenAnalisis { id: ID! fecha: FechaHora! cantidadAnalizadas: Int! truncado: Boolean! versionModelo: VersionModelo! }
type PaginaResumenAnalisis { items: [ResumenAnalisis!]! pagina: Int! tamanio: Int! total: Int! }

type Grupo { grupo: Int! descripcion: String! cantidad: Int! idsCampania: [ID!]! }
type Anomalia { idCampania: ID! nombreParcela: String! cultivo: String! puntaje: Decimal! motivos: [String!]! campania: Campania }
type Excluida { idCampania: ID! motivo: String! }

type Analisis {
  id: ID!
  fecha: FechaHora!
  cantidadAnalizadas: Int!
  truncado: Boolean!
  grupos: [Grupo!]!
  anomalias: [Anomalia!]!
  excluidas: [Excluida!]!
  versionModelo: VersionModelo!
  orientativo: Boolean!
  aviso: String!
}
```

- Los campos raíz son anulables para que un servicio caído no anule toda la respuesta (constitución §4).
- Los objetos `{ "INSUMO": "…", … }` de gestión e IA se entregan como `[MontoPorCategoria!]!`, en el orden del enum `CategoriaCosto`, sin cambiar los montos.
- `Labor.idParcela`, `Labor.idCampania` e `Incidencia.idParcela` se conservan para que React pueda mostrar algo aunque el campo anidado falle.
- Los tipos de este bloque se escribieron a partir de las specs de cada servicio. Los campos que una spec no detalla (`Produccion`, `Advertencia`, `ResumenAnalisis`) se confirman contra el OpenAPI real en T02; si difieren, prevalece el servicio y este bloque se corrige en el mismo commit.

## 2.4 Resolución de cada campo

| Campo | Llamada | Notas |
|---|---|---|
| `parcelas`, `cultivos`, `campanias`, `insumos`, `estadoInventario`, `analisis` | Listado del servicio con los mismos parámetros | La página se copia tal cual |
| `campaniasFinalizadas` | `GET /campanias/historicos` | Filtros con los mismos nombres |
| `campania(id)` y todo campo `campania` / `parcela` / `cultivo` / `insumo` anidado | `GET /<recurso>/{id}` mediante un `DataLoader` por recurso | `404` → `null` |
| `Campania.indicadores`, `.costos`, `.produccion` | `GET /campanias/{id}/...` mediante `DataLoader` | `costos` usa `tamanio=1`: solo se leen `costoTotal` y `subtotalesPorCategoria`. `produccion`: `404 PRODUCCION_NO_REGISTRADA` → `null` |
| `Campania.predicciones` | `GET /predicciones?idCampania=` | — |
| `Campania.labores`, `Campania.incidencias` | `GET /labores?idCampania=`, `GET /incidencias?idCampania=` | Los filtros obligatorios de operaciones se cumplen con `idCampania` |
| `labores`, `incidencias` | Listado con el filtro recibido | Sin `mias`: la cuenta de servicio no es el usuario |
| `analisisPorId` | `GET /analisis/{id}` | `404 ANALISIS_NO_ENCONTRADO` → `null` |

Antes de cada llamada, el resolver verifica el rol con `exigirRol(contexto, roles)` según 1.3. Si el rol no alcanza, lanza `SIN_PERMISO` sin llamar.

Los `DataLoader` se crean por solicitud en el contexto. Como los servicios no tienen consultas por lote, la función de lote hace una llamada por ID distinto, en paralelo.

## 2.5 Seguridad (`src/seguridad/`)

- **`validarToken`**: `jwtVerify` de `jose` con `createRemoteJWKSet(KEYCLOAK_JWKS_URI, { timeoutDuration: 1500 })`, `issuer` y `audience`. El tiempo límite reemplaza al de 5 s que trae `jose` por defecto. Lee los roles de `realm_access.roles`. Si las claves no se pueden obtener (error o tiempo agotado), lanza un error propio que el middleware traduce a `503 AUTENTICACION_NO_DISPONIBLE`.
- **Middleware de autenticación** sobre `/api/graphql` (después de la correlación, antes de Apollo): sin header `Bearer`, token inválido o sin `administrador` ni `gerencia` → respuesta HTTP con `RespuestaError` (401 o 403). Si es válido, guarda `{ sub, roles }` para el contexto de Apollo.
- **`exigirRol`**: función pura usada por los resolvers con la tabla de 1.3 (una constante `PERMISOS` por campo, que también usa el test de permisos).
- La protección CSRF de Apollo queda activa (por defecto): React envía `Content-Type: application/json`, que el gateway ya permite en CORS.
- **CORS (`src/web/cors-desarrollo.ts`):** el servidor no usa el middleware `cors` ni `startStandaloneServer` (que agrega `Access-Control-Allow-Origin: *`): el CORS de React lo aplica el gateway. Única excepción, solo si `NODE_ENV` no es `production` y el header `Origin` es `https://sandbox.embed.apollographql.com` o `https://studio.apollographql.com`. La página de Sandbox que muestra Apollo en `http://localhost:4000/api/graphql` embebe Sandbox desde ese dominio, y sus consultas llegan desde otro origen. Para esos dos orígenes:
  - `OPTIONS` (verificación previa, sin token): responde `204` ahí mismo, sin pasar por la autenticación, con `Access-Control-Allow-Origin` igual al origen, `Access-Control-Allow-Methods: GET, POST, OPTIONS`, `Access-Control-Allow-Headers` igual a lo pedido en `Access-Control-Request-Headers` y `Access-Control-Max-Age: 3600`.
  - Demás métodos: agrega `Access-Control-Allow-Origin` igual al origen y `Access-Control-Expose-Headers: X-Correlation-Id`, y sigue a la autenticación (la consulta exige token).
  - Sin `Access-Control-Allow-Credentials`: el token viaja en `Authorization`, no en cookies.
  - Cualquier otro origen, o cualquier origen en producción: ningún header de CORS. Un `OPTIONS` de otro origen sigue de largo como cualquier solicitud.
- **Orden de los middleware de Express:** correlación → registro de acceso → CORS de desarrollo → autenticación (solo `/api/graphql`) → Apollo. Las rutas de salud van antes de la autenticación.
- Las solicitudes de React llegan con el origen del frontend, que no está en la lista, así que el servidor no agrega nada. Aunque lo hiciera, el `DedupeResponseHeader` del gateway conserva su propio valor (`spec-enrutamiento.md` 2.2).

## 2.6 Cliente del gateway (`src/fuentes/`)

- **Plazo de la consulta:** empieza **al recibir la solicitud**, no al crear el contexto de Apollo, que se crea después de la autenticación. El middleware `correlacion` (el primero, 2.8) crea, para `/api/graphql`, un `AbortController` y un temporizador de `GRAPHQL_PLAZO_CONSULTA_MS` que llama a `abort(new PlazoConsultaVencido())`, y guarda la señal en `res.locals.senalPlazo`. El contexto de Apollo reutiliza esa señal (`senalPlazo`), igual que los `DataLoader` viven en él, así que solo afecta a esa solicitud. El temporizador se limpia cuando la respuesta termina o la conexión se cierra (`res.on('close')`), también si la autenticación respondió `401`, `403` o `503` antes de llegar a Apollo.
  - Así el tiempo de validación del token del usuario (hasta 1,5 s si las claves no están en caché, 2.5) se descuenta del plazo, y la respuesta sigue llegando antes de los 5 s (CE-GQL-05).
- **`TokenServicio`**: client credentials contra `KEYCLOAK_TOKEN_URL`, en caché hasta 30 s antes de vencer, con una sola solicitud en curso a la vez, que comparten todas las consultas que lo necesitan en ese momento.
  - La obtención usa su propio tiempo límite (`AbortSignal.timeout(2000)`) y **nunca** recibe la señal del plazo de una consulta: si la recibiera, al vencer el plazo de una consulta fallarían todas las que esperan el mismo token.
  - `obtener(senalPlazo)`: cada consulta espera la promesa compartida compitiendo contra su propio plazo. Si su plazo vence primero, solo esa consulta deja de esperar (`PlazoConsultaVencido`) y la obtención sigue para las demás.
  - `invalidar()` descarta el token en caché.
- **`ClienteGateway.get(ruta, parametros, contexto)`**:
  1. Si la `senalPlazo` ya se disparó, lanza `DEPENDENCIA_NO_DISPONIBLE` sin llamar y sin descontar del presupuesto.
  2. Descuenta una llamada del presupuesto de la solicitud (`GRAPHQL_MAXIMO_LLAMADAS`); si no quedan, lanza `CONSULTA_DEMASIADO_COMPLEJA` sin llamar.
  3. Obtiene el token con `TokenServicio.obtener(senalPlazo)`.
  4. `fetch` a `API_GATEWAY_URL + ruta` con `Authorization: Bearer <token de servicio>`, `X-Correlation-Id` y la señal `AbortSignal.any([AbortSignal.timeout(GRAPHQL_TIEMPO_LIMITE_LLAMADA_MS), senalPlazo])`. Así cada llamada dura como máximo lo menor entre su tiempo límite y lo que queda del plazo. La lectura del cuerpo (`res.json()`) usa la misma señal y queda dentro del mismo manejo de errores: un corte puede ocurrir mientras se lee.
  5. Ante `401`, `invalidar()` y repite una vez, volviendo al paso 1 (cuenta como otra llamada y solo se hace si el plazo no venció).
  6. Traduce el resultado:

  | Resultado | Error de campo |
  |---|---|
  | `2xx` | — (devuelve el JSON tal cual) |
  | `404` en una búsqueda por ID | — (devuelve `null`) |
  | `400` | `DATOS_INVALIDOS` con los `detalles` del servicio |
  | `403` | `ERROR_INTERNO` + log de error ("permiso faltante en el realm") |
  | `503` o `504` del gateway | `DEPENDENCIA_NO_DISPONIBLE` + log de advertencia |
  | Corte por tiempo límite de la llamada (`DOMException` `TimeoutError`, motivo de `AbortSignal.timeout`), en `fetch` o al leer el cuerpo | `DEPENDENCIA_NO_DISPONIBLE` + log de advertencia con `causa = TIEMPO_LIMITE_LLAMADA` |
  | Corte por plazo de la consulta (`PlazoConsultaVencido`, motivo de `senalPlazo`), en `fetch`, al leer el cuerpo o esperando el token | `DEPENDENCIA_NO_DISPONIBLE` + log de advertencia con `causa = PLAZO_CONSULTA` |
  | Conexión rechazada o nombre que no se resuelve (`TypeError` de `fetch` con su `cause`), token de servicio no disponible | `DEPENDENCIA_NO_DISPONIBLE` + log de advertencia |
  | Otro | `ERROR_INTERNO` + log de error |

  Con `AbortSignal.any`, el error que lanza `fetch` es el motivo de la señal que se disparó primero; por eso el plazo se aborta con un error propio y no con el `AbortError` sin motivo: así el log distingue las dos causas.

- Un cliente por servicio (`gestion.fuente.ts`, `inventario.fuente.ts`, `operaciones.fuente.ts`, `ia.fuente.ts`) con un método por endpoint de 1.3. Solo arma rutas y parámetros.
- El presupuesto y el contador de llamadas viven en el contexto de la solicitud; el log de acceso los lee al final.

## 2.7 Errores (`src/web/errores.ts`)

- Clase `ErrorCampo(codigo, mensaje, detalles?)` que extiende `GraphQLError` con `extensions: { codigo, idCorrelacion, detalles }`.
- `formatError` de Apollo: deja pasar los `ErrorCampo`; convierte los errores de sintaxis y validación de GraphQL (incluidos los argumentos fuera de rango) en `DATOS_INVALIDOS`, y cualquier otro error en `ERROR_INTERNO` sin traza ni mensaje original (el original va al log).
- Los argumentos `tamanio` y `limite` se validan en el resolver (1 a 50) antes de llamar.
- `RespuestaError` (HTTP) igual a la de los microservicios: `codigo`, `mensaje`, `detalles` (lista vacía) e `idCorrelacion`.

## 2.8 Correlación y log de acceso (`src/web/`)

- **`correlacion`** (primer middleware de Express): valida `[A-Za-z0-9-]{1,64}` o genera un UUID con `crypto.randomUUID()`; lo guarda en `res.locals` y lo agrega a la respuesta. En `/api/graphql` además inicia el plazo de la consulta (2.6).
- **`registroAcceso`**: al terminar la respuesta (`res.on('finish')`), escribe una línea JSON en la salida estándar: `fecha`, `nivel`, `mensaje`, `idCorrelacion`, `operacion` (`operationName` o `anonima`), `estado` (HTTP), `duracionMs`, `cantidadLlamadas`, `cantidadErrores` y `sub`. Nunca el token, la consulta ni las variables.
- Un log `warn`/`error` por llamada fallida con `idCorrelacion`, `servicio`, `ruta` (sin parámetros), `estado` y `duracionMs`.
- Logger propio de ~30 líneas sobre `console`/`process.stdout`, con el formato JSON de una línea de los demás servicios; sin librería de logs.

## 2.9 Salud

`GET /salud`, `/salud/liveness` y `/salud/readiness` responden `200 { "estado": "UP" }` sin token. La readiness no consulta Keycloak ni los servicios (RNF-08). Las tres quedan fuera de `/api/graphql` y el gateway no las expone (constitución del gateway §1).

## 2.10 Realm de Keycloak

- `docker/keycloak/realms/realm-agro.json`: agregar a `agro-web` y `agro-pruebas` un `oidc-audience-mapper` `audiencia-graphql-server` con `included.custom.audience = graphql-server`, igual que los cuatro existentes. Los clients de servicio no cambian.
- `scripts/verificar-realm.py`: las audiencias esperadas de los tokens de usuario incluyen `graphql-server`.
- `specs/spec-keycloak-realm.md`: RQ-KC-03 menciona la quinta audiencia, con una línea en su historial que remite a esta spec.
- Aplicar el cambio requiere borrar el realm y reiniciar Keycloak (README §7).

## 2.11 Empaquetado, entorno y pipeline

- **`Dockerfile`** de dos etapas como el de `servicio-inventario`: `npm ci`, `npm run build` (`tsc`), `npm prune --omit=dev`; imagen final `node:24-alpine`, usuario `node`, `CMD ["node", "dist/main.js"]`. Copia también `esquema.graphql`. **`.dockerignore`**: `node_modules`, `dist`, `coverage`, `specs`, `Constitucion.md`.
- **Scripts:** `dev` (`tsx watch src/main.ts`), `build`, `start`, `lint`, `test` (`jest --runInBand`).
- **`.github/workflows/graphql-server.yml`**, copia del de `servicio-inventario` sin Docker en los tests (por eso `ubuntu-latest`): `npm ci`, `lint`, `build`, `test -- --coverage` con umbral del 80 % y `docker build`.
- **`docker-compose.yml`**: al servicio `graphql-server` se le agregan `PORT: 4000` y `KEYCLOAK_AUDIENCE: graphql-server`. El puerto `4000` se sigue publicando para usar Apollo Sandbox en local (con un token de `agro-pruebas`).
- **`README.md`**: `graphql-server` pasa a la lista de servicios con código; la fila de variables suma `KEYCLOAK_AUDIENCE`, `GRAPHQL_TIEMPO_LIMITE_LLAMADA_MS`, `GRAPHQL_PLAZO_CONSULTA_MS` y `GRAPHQL_MAXIMO_LLAMADAS`; el comando de tests (`./scripts/ejecutar.sh graphql-server npm test`).

## 2.12 Tests

Todos en `test/`, con `supertest` contra la aplicación de Express.

- **`soporte/gateway-simulado.ts`**: un servidor HTTP de Node en un puerto aleatorio que hace de gateway (rutas registradas por cada test, con demora y código configurables, y que registra cada llamada recibida con sus headers) y de Keycloak (JWKS y endpoint de token). Genera un par de claves RSA y firma tokens de usuario con `iss`, `aud`, `exp`, `sub` y roles configurables, más una segunda clave fuera del JWKS.
- **`soporte/respuestas/`**: respuestas de ejemplo de cada servicio, copiadas de su OpenAPI en T02.

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `escalares.spec.ts` | `Decimal`, `Fecha` y `FechaHora` aceptan y devuelven texto; rechazan números y formatos inválidos |
| Unitario | `permisos.spec.ts` | `exigirRol` con cada rol y la constante `PERMISOS` |
| Unitario | `cliente-gateway.spec.ts` | Tabla de traducción de 2.6 (incluidos los dos tipos de corte, en `fetch` y al leer el cuerpo), renovación ante `401` solo si el plazo lo permite, plazo vencido sin descontar del presupuesto, presupuesto agotado |
| Unitario | `token-servicio.spec.ts` | Una sola obtención para varias consultas; el plazo vencido de una no corta la obtención ni a las demás; tiempo límite propio de la obtención |
| Integración | `gestion.int-spec.ts` | Historias 1 y 2: valores idénticos a la respuesta simulada, una llamada por parcela repetida, `null` ante `404` |
| Integración | `inventario.int-spec.ts` | Historia 3 |
| Integración | `operaciones.int-spec.ts` | Historia 5, incluido el error `DATOS_INVALIDOS` reenviado |
| Integración | `ia.int-spec.ts` | Historia 4 |
| Integración | `seguridad.int-spec.ts` | Historia 6: 401 por cada causa, 403 de técnico, `SIN_PERMISO` por campo con cada rol de la tabla 1.3 (recorriendo `PERMISOS`), sin llamadas cuando el rol no alcanza, `mutation` rechazada, `503 AUTENTICACION_NO_DISPONIBLE` con el JWKS en `500` y con el JWKS sin responder (en menos de 2 s) |
| Integración | `cors.int-spec.ts` | Caso borde de CORS: fuera de producción, `OPTIONS` desde `https://sandbox.embed.apollographql.com` sin token → `204` con los headers de 2.5 y sin llamadas a servicios; un `POST` desde ese origen lleva `Access-Control-Allow-Origin` y sigue exigiendo token; otro origen (por ejemplo `http://localhost:9000`) no recibe ningún header de CORS, ni en `OPTIONS` ni en `POST`; con `NODE_ENV=production`, tampoco los orígenes de Apollo |
| Integración | `resiliencia.int-spec.ts` | Historia 7 y casos borde: servicio en `503`, demora mayor al tiempo límite, token de servicio no disponible, presupuesto agotado, readiness `UP` sin servicios, `403` del servicio → `ERROR_INTERNO`; escenario 6 de tres niveles con servicios lentos, que responde antes de 4,7 s con los campos parciales; escenario 7, con el JWKS demorado 1 s y un servicio que nunca responde, también antes de 4,7 s desde la recepción (CE-GQL-05) |
| Integración | `correlacion.int-spec.ts` | Historia 8: header propagado a cada llamada, generado si falta, en `extensions` y en el log (sin token ni consulta) |
| Integración | `rendimiento.int-spec.ts` | CE-GQL-02 |

## 2.13 Decisiones del plan

| ID | Decisión | Motivo |
|---|---|---|
| D-GQL-01 | Express delante de Apollo, en lugar de `startStandaloneServer` | El servidor necesita `/salud`, la correlación y el rechazo HTTP 401/403 antes de ejecutar la consulta. |
| D-GQL-02 | Validación del token en un middleware y permisos por campo en los resolvers | El 401/403 general se resuelve una vez por solicitud; la tabla de 1.3 depende del campo. |
| D-GQL-03 | Máximo de llamadas por consulta en lugar de un análisis de profundidad o complejidad | Mide lo que importa (la carga sobre los servicios) sin otra dependencia. |
| D-GQL-04 | Páginas de hasta 50 elementos y máximo de 200 llamadas | El peor caso del tablero (50 campañas con indicadores, cada una con parcela y cultivo distintos) son 151 llamadas y entra en el máximo. Una consulta que además anida labores o predicciones por campaña lo supera y recibe `CONSULTA_DEMASIADO_COMPLEJA`: React debe pedirlas por campaña. |
| D-GQL-05 | Tests con un gateway simulado en el propio proceso, sin contenedores | No hay base de datos ni broker; como en el gateway (D-GW-04), Keycloak se simula con un JWKS propio. |
| D-GQL-06 | Tiempo límite de 4 s por llamada y plazo total de 4,5 s por consulta | El tiempo límite por llamada solo no acota la consulta: cada nivel anidado espera al anterior, y tres niveles con un servicio lento suman 12 s, más que los 10 s del gateway. El plazo total hace que GraphQL siempre responda en menos de 5 s (RNF-05) y antes que el gateway, con la respuesta parcial. Se descartó dar a `/api/graphql` un tiempo límite propio más largo en el gateway: su constitución (§4) solo lo admite si la spec del servicio acepta respuestas más lentas, y RNF-05 lo prohíbe. |
| D-GQL-07 | Sin CORS en el servidor, salvo Apollo Sandbox y Studio fuera de producción | El CORS de React es del gateway; un `*` del servidor llegaría al navegador cuando el gateway no agrega su header. La excepción es necesaria porque Sandbox (§1.7.2 del documento de requisitos) hace sus consultas desde un dominio de Apollo, y por el gateway no sirve: al abrir la página el navegador no envía token y recibe `401`. Implementación propia de unas 20 líneas, sin la dependencia `cors`. |

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

- [ ] **T01** — Crear el proyecto (`package.json`, `tsconfig.json`, ESLint, Jest), `config.ts`, `main.ts`, `app.ts` y las rutas de salud. *Hecho cuando:* `./scripts/ejecutar.sh graphql-server npm run build` compila y `/salud/readiness` responde `UP` en un test.
- [ ] **T02** — Revisar el OpenAPI real de los cuatro servicios para cada endpoint de 1.3; guardar una respuesta de ejemplo de cada uno en `test/soporte/respuestas/` y corregir 2.3 si algún campo difiere. *Hecho cuando:* cada tipo de 2.3 tiene su respuesta de ejemplo.
- [ ] **T03** — Implementar `correlacion`, `registroAcceso`, el logger, `RespuestaError` y `cors-desarrollo`, en el orden de 2.5, con `gateway-simulado.ts`. *Hecho cuando:* pasan `cors.int-spec.ts` y `correlacion.int-spec.ts`, salvo lo que depende de llamadas a servicios.
- [ ] **T04** — Implementar `validarToken`, el middleware de autenticación y `exigirRol` con `PERMISOS`. *Hecho cuando:* pasan `permisos.spec.ts` y los escenarios 1 a 3 de la historia 6.
- [ ] **T05** [P] — Agregar la audiencia `graphql-server` al realm, a `verificar-realm.py` y a `spec-keycloak-realm.md` (2.10). *Hecho cuando:* con el realm reimportado, `python3 scripts/verificar-realm.py` termina con código 0.
- [ ] **T06** — Implementar el plazo de la consulta, `TokenServicio` y `ClienteGateway` (2.6). *Hecho cuando:* pasan `token-servicio.spec.ts` y `cliente-gateway.spec.ts`.
- [ ] **T07** — Escribir el esquema, los escalares, `formatError` y los resolvers de gestión con sus `DataLoader`. *Hecho cuando:* pasan `escalares.spec.ts` y `gestion.int-spec.ts`.
- [ ] **T08** [P] — Resolvers de inventario. *Hecho cuando:* pasa `inventario.int-spec.ts`.
- [ ] **T09** [P] — Resolvers de operaciones. *Hecho cuando:* pasa `operaciones.int-spec.ts`.
- [ ] **T10** [P] — Resolvers de IA. *Hecho cuando:* pasa `ia.int-spec.ts`.
- [ ] **T11** — Completar `seguridad.int-spec.ts`, `resiliencia.int-spec.ts` y `correlacion.int-spec.ts`. *Hecho cuando:* pasan completos.
- [ ] **T12** [P] — Escribir `rendimiento.int-spec.ts` (CE-GQL-02).
- [ ] **T13** — Escribir el `Dockerfile`, `.dockerignore` y `.github/workflows/graphql-server.yml`; actualizar `docker-compose.yml` y `README.md` (2.11). *Hecho cuando:* `npm test -- --coverage` pasa con ≥ 80 %, `docker build` construye la imagen y `docker compose --profile graphql up -d graphql-server` arranca con `/salud` en `UP`.
- [ ] **T14** — Prueba manual de punta a punta (CE-GQL-03, requiere `api-gateway/specs/spec-ruta-graphql.md` implementada y T05). *Hecho cuando:* la consulta del tablero con un token de `gerencia.prueba` (`agro-pruebas`) contra `http://localhost:8080/api/graphql` devuelve los mismos valores que las llamadas REST, y el mismo `idCorrelacion` aparece en los logs del gateway, de `graphql-server` y de `servicio-gestion`.
- [ ] **T15** — Verificación final: `npm run lint`, `npm run build` y `npm test -- --coverage` en verde, y los criterios CE-GQL-01, CE-GQL-02, CE-GQL-04 y CE-GQL-05 cubiertos por al menos un test (CE-GQL-03 queda en T14).
