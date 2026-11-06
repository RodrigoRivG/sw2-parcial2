# Realm de Keycloak para desarrollo — sistema

| Campo | Valor |
|---|---|
| Alcance | Todo el sistema (no pertenece a un microservicio) |
| Archivo | `specs/spec-keycloak-realm.md` |
| Estado | Implementada (2026-11-04) |
| Referencias | Constituciones de `servicio-gestion`, `servicio-inventario`, `servicio-operaciones` (v2.8.0) y `api-gateway` (v1.0.0), sección Seguridad |
| Trazabilidad | CU-19, CU-23 · RF-28, RF-32 · RN-15, RN-16 · RNF-02, RNF-03, RNF-19 |
| Desbloquea | `api-gateway/specs/spec-enrutamiento.md` T12 y `servicio-operaciones/specs/spec-saga.md` CE-SAG-05 (pruebas de punta a punta) |

Contenido:

1. [Spec](#1-spec): qué debe tener el realm.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

Los tres servicios de negocio y el gateway ya validan tokens de Keycloak, pero el realm `agro` no existe: `docker/keycloak/realms/` está vacío. Sin él no hay tokens, y nada se puede probar de punta a punta.

Lo que el realm debe contener **ya está fijado por el código y las specs implementadas**; esta spec lo reúne en un solo lugar y no inventa permisos nuevos:

| Quién lo exige | Qué |
|---|---|
| Los tres servicios (`realm_access.roles`) | Roles de realm, no de cliente |
| Constituciones, tabla de permisos | `administrador`, `gerencia`, `tecnico_campo` |
| `servicio-gestion` RQ-INT-06, D-11 | `lectura_gestion` (`servicio-ia`, GraphQL) y `estado_campania` (`servicio-operaciones`, GraphQL). n8n sin permisos en gestión (AC-02). |
| `servicio-inventario` D-10 | `lectura_inventario` (`servicio-ia`, GraphQL, n8n) |
| `servicio-operaciones` D-10 | `lectura_operaciones` (n8n, `servicio-ia`, GraphQL); la cuenta de `servicio-operaciones` lleva `servicio-gestion` en `aud` |
| Cada servicio valida su propia audiencia | `aud` con `servicio-gestion`, `servicio-inventario`, `servicio-operaciones` o `servicio-ia` según a quién llame el token |
| `servicio-operaciones` D-11 | El responsable de una labor sale de `name` (o `preferred_username`) |
| Docker Compose (`x-keycloak-env`) | Realm `agro`, emisor `http://localhost:8180/realms/agro` |

## 1.1 Escenarios de usuario y pruebas

### Historia 1 — Iniciar sesión con un rol (Prioridad: P1)

Como usuario de prueba, quiero obtener un token con mis roles y las audiencias de los servicios, para usar el sistema a través del gateway (CU-19, RF-28).

**Prueba independiente:** con Keycloak levantado, se pide un token por cada usuario de prueba y se revisan sus claims.

**Escenarios de aceptación:**

1. **Dado** el usuario `admin.prueba`, **cuando** obtiene un token, **entonces** `iss` es `http://localhost:8180/realms/agro`, `realm_access.roles` contiene `administrador`, `aud` contiene `servicio-gestion`, `servicio-inventario`, `servicio-operaciones` y `servicio-ia`, y el token trae `name` y `preferred_username`.
2. Lo mismo para `tecnico.prueba` (`tecnico_campo`) y `gerencia.prueba` (`gerencia`).
3. **Dado** el usuario `multirol.prueba` con `administrador` y `gerencia`, **entonces** su token trae ambos roles (RN-15: un usuario puede tener más de un rol).
4. **Dado** cualquiera de esos tokens, **cuando** se usa contra el gateway en una ruta que su rol permite, **entonces** el servicio responde `200`; en una que no permite, `403 SIN_PERMISO` del servicio (no del gateway).

### Historia 2 — Cuentas de servicio con permisos mínimos (Prioridad: P1)

Como servicio técnico (`servicio-operaciones`, `servicio-ia`, GraphQL, n8n), quiero obtener un token con client credentials que solo me permita lo que mi integración necesita.

**Escenarios de aceptación:**

1. **Dado** el client `servicio-operaciones`, **cuando** pide un token con client credentials, **entonces** tiene el rol `estado_campania`, `aud` contiene `servicio-gestion`, y `GET /api/gestion/v1/campanias/{id}/estado` a través del gateway responde `200` (o `404 CAMPANIA_NO_ENCONTRADA`).
2. **Dado** ese mismo token, **cuando** intenta `GET /api/gestion/v1/parcelas`, **entonces** gestión responde `403 SIN_PERMISO`; y contra `/api/inventario/**`, `401` (inventario no está en su `aud`).
3. **Dado** los clients `servicio-ia`, `graphql-server` y `n8n`, **entonces** cada token tiene exactamente los roles y audiencias de la tabla de 1.2 (RQ-KC-04).
4. **Dado** un client de servicio con un secreto incorrecto, **entonces** Keycloak responde `401` y no emite token.

### Historia 3 — Levantar el realm sin pasos manuales (Prioridad: P1)

Como desarrollador, quiero que `docker compose --profile auth up` deje el realm listo, sin configurar nada en la consola de Keycloak (RNF-19).

**Escenarios de aceptación:**

1. **Dado** un volumen de PostgreSQL sin el realm, **cuando** arranca Keycloak, **entonces** importa `docker/keycloak/realms/realm-agro.json` y los escenarios de las historias 1 y 2 se cumplen.
2. **Dado** el repositorio, **entonces** no contiene ningún secreto de client ni contraseña de usuario: el JSON usa variables de entorno que Docker Compose toma del `.env` (RNF-03).
3. **Dado** que el realm ya existe (Keycloak ya arrancó antes), **entonces** la importación se omite sin error; para aplicar cambios del JSON se borra el realm (ver 2.5).

### Historia 4 — Gestionar usuarios desde Angular (Prioridad: P2)

Como administrador, quiero crear cuentas, asignar roles y activar o desactivar usuarios desde Angular mediante la API de administración de Keycloak (RF-32, CU-23).

**Escenarios de aceptación:**

1. **Dado** un token de `admin.prueba` obtenido con el client web, **cuando** llama a `GET http://localhost:8180/admin/realms/agro/users`, **entonces** recibe `200`.
2. **Dado** un token de `gerencia.prueba` o `tecnico.prueba`, **entonces** la misma llamada responde `403`.
3. **Dado** un token de cuenta de servicio, **entonces** también responde `403`.

### Casos borde

- **Emisor según el origen:** el token debe tener el mismo `iss` si se pide desde el navegador (`localhost:8180`) o desde un contenedor (`keycloak:8080`). Docker Compose ya lo resuelve con `KC_HOSTNAME`; el realm no debe fijar otro `frontendUrl`.
- **Token de usuario contra un servicio fuera de su `aud`:** no ocurre con los clients de usuario, porque llevan las cuatro audiencias. Un token emitido para un client ajeno (por ejemplo, `account`) responde `401` en los servicios.
- **Secreto vacío en el `.env`:** si falta una variable de secreto, la importación no debe crear un client sin secreto. Por eso los secretos de desarrollo tienen valor en `.env.example` y el script de verificación (T03) falla si un client confidencial obtiene token con un secreto vacío.

## 1.2 Requisitos

- **RQ-KC-01:** realm `agro`, habilitado, con el login por usuario y contraseña de Keycloak, sin registro público de usuarios.
- **RQ-KC-02:** roles de realm: `administrador`, `gerencia`, `tecnico_campo`, `lectura_gestion`, `estado_campania`, `lectura_inventario`, `lectura_operaciones`, `lectura_ia` y `reportes_ia`. Ninguno es compuesto. Los roles por defecto del realm (`default-roles-agro`) no incluyen ninguno de ellos.
- **RQ-KC-03:** clients de usuario, públicos, con Authorization Code y PKCE (`S256`):

  | Client | Para | Redirecciones (desarrollo) |
  |---|---|---|
  | `agro-web` | La aplicación contenedora de single-spa y sus tres microfrontends, que comparten la sesión (Módulo 6) | `http://localhost:9000/*` (provisional, como `CORS_ORIGENES_PERMITIDOS`) |
  | `agro-movil` | Flutter con `flutter_appauth` (Módulo 7) | `com.agrosystem.campo:/oauthredirect` (provisional) |

  Ambos agregan a `aud` las cuatro audiencias de los servicios.

- **RQ-KC-04:** clients de servicio, confidenciales, solo con client credentials (sin login de usuario):

  | Client | Roles | `aud` | Origen |
  |---|---|---|---|
  | `servicio-operaciones` | `estado_campania` | `servicio-gestion` | gestión RQ-INT-06, operaciones D-10 |
  | `servicio-ia` | `lectura_gestion`, `lectura_inventario`, `lectura_operaciones` | `servicio-gestion`, `servicio-inventario`, `servicio-operaciones` | constitución de IA §6 (solo lectura) |
  | `graphql-server` | `lectura_gestion`, `estado_campania`, `lectura_inventario`, `lectura_operaciones`, `lectura_ia` | `servicio-gestion`, `servicio-inventario`, `servicio-operaciones`, `servicio-ia` | RF-27; `lectura_ia`: `servicio-ia/specs/spec-prediccion.md` (lectura de predicciones y análisis) |
  | `n8n` | `lectura_inventario`, `lectura_operaciones`, `reportes_ia` | `servicio-inventario`, `servicio-operaciones`, `servicio-ia` | inventario D-10, operaciones D-10, gestión AC-02; `reportes_ia`: `servicio-ia/specs/spec-reportes.md` (pedir y descargar reportes programados) |

- **RQ-KC-05:** el rol `administrador` permite gestionar usuarios con la API de administración de Keycloak (RF-32) mediante los roles del client `realm-management` `view-users`, `query-users`, `query-groups` y `manage-users`, asignados al usuario administrador de prueba (no como compuesto del rol de realm, para no darlos a cuentas de servicio).

  > Nota: `manage-users` permite asignar cualquier rol de realm. Restringirlo (permisos finos de Keycloak) queda fuera del alcance del examen.

- **RQ-KC-06:** usuarios de prueba, solo para desarrollo, con nombre y apellido (para `name`) y correo verificado:

  | Usuario | Roles de realm |
  |---|---|
  | `admin.prueba` | `administrador` (y los roles de `realm-management` de RQ-KC-05) |
  | `tecnico.prueba` | `tecnico_campo` |
  | `gerencia.prueba` | `gerencia` |
  | `multirol.prueba` | `administrador`, `gerencia` |

- **RQ-KC-07:** un client de pruebas `agro-pruebas`, público y **solo con password grant** (direct access grants), con las mismas audiencias que `agro-web`, para que los scripts y las pruebas manuales obtengan tokens de usuario con `curl`. No se crea en la nube.
- **RQ-KC-08:** secretos de los clients y contraseña de los usuarios de prueba solo en variables de entorno (placeholders `${VARIABLE}` en el JSON, que Keycloak reemplaza al importar).
- **RQ-KC-09:** vigencias por defecto de Keycloak (token de acceso de 5 minutos). Ningún servicio depende de otro valor: operaciones renueva su token 30 s antes de vencer (D-12).

## 1.3 Criterios de éxito

- **CE-KC-01:** `scripts/verificar-realm.py` comprueba los escenarios de las historias 1, 2 y 4 (claims de cada token y respuestas de la API de administración) y termina con código 0.
- **CE-KC-02:** con los perfiles `saga`, `gateway` y `auth`, una labor con insumos registrada por `tecnico.prueba` a través del gateway queda `CONFIRMADA` con el stock descontado y el costo registrado; con stock insuficiente, `RECHAZADA` (CE-SAG-05 de operaciones y T12 del gateway).
- **CE-KC-03:** `git grep` no encuentra secretos ni contraseñas en `docker/keycloak/realms/`.

## 1.4 Supuestos

- El realm de la nube se crea con el mismo JSON y otras variables (secretos reales, redirecciones de CloudFront y del paquete de Flutter). Los usuarios de prueba y `agro-pruebas` no se importan allí: el plan de despliegue lo decidirá.
- Las URL de redirección de `agro-web` y `agro-movil` son provisionales hasta que existan esas aplicaciones.

## 1.5 Fuera de alcance

- Los flujos de login de los frontends y de Flutter (cada uno en su spec).
- Permisos finos de administración, temas visuales y correo de Keycloak.
- Roles de `servicio-ia` más allá de su audiencia.

---

# 2. Plan

## 2.1 Archivo del realm

- `docker/keycloak/realms/realm-agro.json`, exportado en el formato de importación de Keycloak 26 (el de `kc.sh export`), **escrito a mano y mínimo**: solo lo que cambia respecto de los valores por defecto, para que se pueda revisar en un diff.
- Audiencias con mappers `oidc-audience-mapper` y `included.custom.audience` (una por audiencia), definidos en el client (`protocolMappers`). Así no hace falta crear un client por cada servicio solo para nombrarlo en `aud`.
- Roles de cuenta de servicio con `serviceAccountClientRoles`/`users` del tipo `service-account-<client>` y sus `realmRoles`.
- Secretos y contraseñas como `${OPERACIONES_CLIENT_SECRET}`, `${IA_CLIENT_SECRET}`, `${GRAPHQL_CLIENT_SECRET}`, `${N8N_CLIENT_SECRET}` y `${KEYCLOAK_CLAVE_USUARIOS_PRUEBA}`.

## 2.2 Docker Compose y `.env.example`

- El servicio `keycloak` recibe esas cinco variables en `environment`.
- `.env.example`: valores de desarrollo para los cuatro secretos (`dev-<client>-secreto`) y `KEYCLOAK_CLAVE_USUARIOS_PRUEBA=prueba123`, con el comentario de que son solo locales. Se agrega `N8N_CLIENT_SECRET`, que hoy no existe.
- Hoy `OPERACIONES_CLIENT_SECRET`, `IA_CLIENT_SECRET` y `GRAPHQL_CLIENT_SECRET` ya se pasan a sus servicios con `${...:-}`; no cambia.
- `README.md` §7 («Keycloak y los tokens»): se reemplaza «Cuando el realm esté listo, expórtalo…» por cómo se importa, los usuarios de prueba y cómo reimportar.

## 2.3 Script de verificación

`scripts/verificar-realm.py` (Python 3 con la biblioteca estándar, ejecutado desde la máquina contra `localhost:8180` y `localhost:8080`; no se usa `jq` porque no viene instalado en WSL):

1. Obtiene un token por usuario de prueba (`agro-pruebas`, password grant) y por cliente de servicio (client credentials).
2. Decodifica el payload y compara `iss`, `aud`, `realm_access.roles` y `name` con las tablas de 1.2.
3. Llama a `GET /admin/realms/agro/users` con cada token de usuario y de servicio (historia 4).
4. Si el gateway y los servicios están arriba, comprueba los escenarios de las historias 1.4 y 2.1–2.2; si no, los informa como omitidos.

Imprime una línea por comprobación y termina con código distinto de 0 si alguna falla.

## 2.4 Prueba de punta a punta

Documentada en el mismo script como una sección opcional (`--saga`): con tokens de `admin.prueba` crea parcela, cultivo y campaña `EN_CURSO` en gestión y un insumo con stock en inventario; con `tecnico.prueba` registra una labor con insumos y consulta su estado hasta que sea terminal (máximo 30 s). Repite con una cantidad mayor al stock para el caso `RECHAZADA`. Verifica el mismo `X-Correlation-Id` en los logs del gateway y de operaciones.

## 2.5 Reimportar

`--import-realm` no sobrescribe un realm existente. Para aplicar cambios del JSON: borrar el realm desde la consola de administración o con `kcadm.sh delete realms/agro` dentro del contenedor y reiniciar Keycloak. No hace falta borrar el volumen de PostgreSQL.

## 2.6 Decisiones

| ID | Decisión | Motivo |
|---|---|---|
| D-KC-01 | Roles de realm, no de cliente | Es lo que leen los tres servicios (`realm_access.roles`). |
| D-KC-02 | Un client web para los tres microfrontends | Comparten sesión y token (Módulo 6); con tres clients habría tres tokens. |
| D-KC-03 | Audiencias como texto (`included.custom.audience`) | No exige un client por servicio; el nombre es el que valida cada uno (`KEYCLOAK_AUDIENCE`). |
| D-KC-04 | Client `agro-pruebas` aparte con password grant | Los clients reales usan solo Authorization Code con PKCE; el password grant queda aislado y no se despliega. |
| D-KC-05 | Secretos por placeholders de importación | Cumple RNF-03 sin pasos manuales. |

---

# 3. Tareas

- [x] **T01** — Escribir `docker/keycloak/realms/realm-agro.json` (realm, roles, clients, mappers, cuentas de servicio y usuarios de prueba). *Hecho cuando:* Keycloak lo importa sin errores en un arranque limpio.
- [x] **T02** — Agregar las variables al servicio `keycloak` de `docker-compose.yml` y a `.env.example`. *Hecho cuando:* `docker compose config` muestra las variables y `git grep` no encuentra secretos en el JSON (CE-KC-03).
- [x] **T03** — Escribir `scripts/verificar-realm.py` (2.3). *Hecho cuando:* pasa las historias 1, 2 y 4 contra Keycloak (CE-KC-01).
- [x] **T04** — Actualizar `README.md` §7 (2.2 y 2.5).
- [x] **T05** — Prueba de punta a punta con los perfiles `saga`, `gateway` y `auth` (`--saga`, 2.4). *Hecho cuando:* se cumple CE-KC-02; se marcan `api-gateway` T12 y `servicio-operaciones` T09 (CE-SAG-05).

## Resultado (2026-11-04)

`python3 scripts/verificar-realm.py --saga` con los perfiles `saga`, `gateway` y `auth`: 71 comprobaciones correctas, 0 fallidas. Incluye la Saga de punta a punta: con 20 kg de un insumo de 100 kg, la labor queda `CONFIRMADA`, el stock baja a 80 kg y gestión registra un costo de `97.00`; con 500 kg queda `RECHAZADA` y el stock no cambia. El mismo `idCorrelacion` aparece en los logs del gateway y de `servicio-operaciones`.

Al probar con los servicios apagados apareció un error del gateway (respondía `500` cuando el nombre del contenedor no se resolvía); se corrigió en `api-gateway` (`spec-enrutamiento.md`, notas de implementación).
