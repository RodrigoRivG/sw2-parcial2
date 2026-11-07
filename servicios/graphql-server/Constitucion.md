# Constitución — Servidor GraphQL (`graphql-server`)

> Reglas no negociables del servidor GraphQL. Prevalecen sobre specs, planes y tareas.
> Si una spec contradice esta constitución, se corrige la spec o se enmienda la constitución; nunca se ignora.
> El servidor GraphQL no es uno de los cuatro microservicios de negocio: no copia sus secciones **[común]** de datos y mensajería, pero respeta su contrato de seguridad, formato de error y correlación. La sección «Convenciones» común se adopta completa.

## 1. Propósito y límites

**Responsable de:**
- Exponer al microfrontend React consultas consolidadas que combinan datos de `servicio-gestion`, `servicio-inventario`, `servicio-operaciones` y `servicio-ia` en una sola respuesta (RF-27, proceso 7, Módulo 9).
- Validar el token del usuario y decidir qué partes de cada consulta puede ver, según sus roles.
- Consultar los microservicios a través del API Gateway con su cuenta de servicio y propagar el `X-Correlation-Id`.

**No es responsable de:**
- Crear, modificar ni borrar datos, ni lanzar procesos de IA (predicciones, análisis, agentes, reportes, clasificaciones). React los pide por REST al servicio dueño, a través del gateway.
- Calcular cifras: sumas, promedios, indicadores, rendimientos o costos. Cada cifra que responde es la que devolvió el servicio dueño (RN-14, constitución de `servicio-gestion` §1).
- Guardar datos: no tiene base de datos ni caché entre solicitudes.
- Emitir tokens ni gestionar usuarios → Keycloak.
- Mensajería: no publica ni consume de RabbitMQ.

**Fuera del alcance:** mutaciones, suscripciones, federación de esquemas, caché de respuestas y consultas persistidas.

**Trazabilidad:** CU-05, CU-14, CU-15, CU-24 · RF-06, RF-18, RF-19, RF-27, RF-33 · RN-13, RN-14, RN-15, RN-16 · RNF-02, RNF-03, RNF-05, RNF-08, RNF-19, RNF-20, RNF-21, RNF-22.

## 2. Stack

- Node.js (LTS) + TypeScript en modo `strict`, con la misma versión de Node que `servicio-inventario` (imagen de desarrollo compartida `docker/node`).
- Apollo Server (Módulo 9 y §1.7.2 del documento de requisitos), en su versión estable vigente al crear el proyecto, fijada en `package.json`.
- Esquema escrito en SDL (archivo `.graphql`), no generado desde clases.
- Validación del JWT con `jose`, la misma librería de `servicio-inventario`.
- Llamadas HTTP con el `fetch` nativo de Node.
- Tests: Jest + Supertest, con el gateway y Keycloak simulados en el propio test. No se levantan contenedores.
- Despliegue: imagen Docker en Azure Container Apps (§1.8.5 del documento de requisitos).
- No se introducen lenguajes, frameworks ni bases de datos nuevas sin una enmienda.

## 3. Arquitectura

- El servidor no tiene dominio ni persistencia: no aplica DDD, Hexagonal ni Clean. Es una capa de composición.
- Se organiza por fuente de datos: un cliente por microservicio y sus resolvers. Un resolver solo llama a su cliente; el cliente solo hace HTTP y traduce errores.
- Ningún resolver calcula, redondea, convierte unidades ni reordena por un criterio propio: copia los valores tal como llegan. Sí puede cambiar la forma (por ejemplo, convertir un objeto `{ "INSUMO": "820.50" }` en una lista de pares) sin cambiar ningún valor.
- Los nombres de tipos, campos y enumeraciones del esquema son los mismos que usan los servicios dueños en su JSON y en su glosario. Si un servicio cambia su contrato, el esquema se ajusta en una spec.
- Dentro de una misma solicitud, una entidad pedida varias veces (por ejemplo, la misma parcela en varias campañas) se consulta una sola vez. Esa caché vive solo durante la solicitud.

### Estructura de directorios

```text
graphql-server/
├── src/
│   ├── main.ts                       # arranque
│   ├── app.ts                        # servidor HTTP + Apollo
│   ├── config.ts                     # variables de entorno
│   ├── esquema/
│   │   ├── esquema.graphql
│   │   ├── escalares.ts
│   │   └── resolvers/                # uno por fuente: gestion, inventario, operaciones, ia
│   ├── fuentes/                      # clientes REST, siempre contra el API Gateway
│   ├── seguridad/                    # validación del token y permisos
│   └── web/                          # correlación, registro de acceso, salud y errores
├── test/
│   ├── unit/
│   └── integration/                  # gateway y Keycloak simulados
├── specs/
├── Dockerfile
├── package.json
├── tsconfig.json
└── Constitucion.md
```

- Los nombres de archivo son de referencia y se fijan en el plan.

## 4. Esquema

- Solo existe el tipo `Query`. No hay `Mutation` ni `Subscription`.
- Los decimales se exponen con un escalar `Decimal` serializado como texto (`"820.50"`), nunca como `Float`, igual que la convención común de los microservicios. Las fechas sin hora usan el escalar `Fecha` (`AAAA-MM-DD`) y las fechas con hora, `FechaHora` (ISO 8601 UTC).
- Cada listado conserva la paginación del servicio dueño: `pagina`, `tamanio` y `total` para gestión, inventario e IA; `limite`, `cursor` y `siguienteCursor` para operaciones. No se inventa una paginación común.
- Todo campo que se resuelve con una llamada adicional a un servicio es anulable: si esa llamada falla, solo ese campo queda en `null` con su error, y el resto de la respuesta llega (RNF-08).
- Los resultados de IA se exponen con `orientativo` y el `aviso` que devuelve `servicio-ia` (RN-13).
- La introspección está habilitada: el esquema es la documentación que pide §1.7.6 del documento de requisitos.

## 5. Seguridad

- Toda consulta exige un JWT de Keycloak. Se validan firma (`KEYCLOAK_JWKS_URI`), emisor (`iss`), audiencia (`aud` = `graphql-server`) y vigencia (`exp`) (RNF-02).
- Pueden usar el servidor los usuarios con rol `administrador` o `gerencia`. Cualquier otro token responde `403 SIN_PERMISO`.
- **Regla de permisos: nunca más de lo que el usuario vería por REST.** Cada campo raíz y cada campo que consulta otro servicio solo se entrega a los roles de usuario que el servicio dueño autoriza para esos datos (la tabla vive en la spec). Si el usuario no tiene el rol, ese campo responde el error `SIN_PERMISO` y queda en `null`. RN-16 se sigue cumpliendo: los servicios vuelven a verificar la cuenta de servicio.
- Hacia los microservicios se usa la cuenta de servicio `graphql-server` (client credentials contra `KEYCLOAK_TOKEN_URL`), con los roles de solo lectura del realm (`lectura_gestion`, `estado_campania`, `lectura_inventario`, `lectura_operaciones`, `lectura_ia`). El token del usuario nunca se reenvía.
- Solo se accede a los microservicios a través del API Gateway (`API_GATEWAY_URL`). Los clientes llegan al servidor a través del gateway, en `/api/graphql`.
- El servidor no emite headers de CORS: los aplica el gateway (`CORS_ORIGENES_PERMITIDOS`). Única excepción: fuera de producción, los orígenes de Apollo Sandbox y Apollo Studio, para probar el esquema contra el puerto 4000 (§1.7.2 del documento de requisitos).
- Las claves de Keycloak se descargan con un tiempo límite propio, para que un Keycloak lento no deje la solicitud esperando sin tope.
- Secretos y configuración solo por variables de entorno (RNF-03). El TLS de la nube lo termina Azure Container Apps (RNF-01).
- Los logs no contienen tokens, secretos, el texto de la consulta ni sus variables; como dato de usuario solo se registra el `sub`.

## 6. Comunicación con los microservicios

- Solo lectura: el servidor solo hace `GET`.
- Cada llamada tiene un tiempo límite propio, configurable, y un solo intento. Única excepción: un `401` renueva el token de la cuenta de servicio y repite una vez.
- Las llamadas independientes de una misma consulta se hacen en paralelo.
- Una consulta tiene un máximo de llamadas a los microservicios, configurable. Al superarlo, los campos restantes responden el error `CONSULTA_DEMASIADO_COMPLEJA`. Así una consulta anidada no puede multiplicar la carga sobre los servicios.
- Cada consulta tiene un plazo total configurable, menor que la meta de RNF-05 (5 s) y que el tiempo límite del gateway. El plazo empieza al recibir la solicitud e incluye la validación del token del usuario. Cada llamada usa el menor entre su tiempo límite y lo que queda del plazo. Al vencer el plazo se cortan las llamadas abiertas, los campos pendientes responden `DEPENDENCIA_NO_DISPONIBLE` y la respuesta parcial se entrega igual.
- El token de la cuenta de servicio es compartido entre solicitudes: su obtención tiene su propio tiempo límite y nunca se cancela por el plazo de una solicitud.

## 7. Errores y observabilidad

- Los errores que impiden ejecutar la consulta (token ausente o inválido, rol insuficiente, Keycloak no disponible) se responden con su código HTTP y el formato común de los microservicios:

```json
{
  "codigo": "NO_AUTENTICADO",
  "mensaje": "Debe iniciar sesión para continuar.",
  "detalles": [],
  "idCorrelacion": "uuid"
}
```

- Los errores de un campo se responden según GraphQL (HTTP `200`, lista `errors`) con `extensions.codigo`, `extensions.idCorrelacion` y, si aplica, `extensions.detalles`. El `mensaje` es apto para mostrar al usuario.
- Un `404` de un servicio para una entidad pedida por ID se responde como `null` sin error. Un `503`, `504`, tiempo agotado o conexión rechazada se responde como `DEPENDENCIA_NO_DISPONIBLE` en ese campo. Un `400` del servicio se responde como `DATOS_INVALIDOS` con sus `detalles`. Un `403` del servicio indica un error de configuración del realm: se registra en el log y se responde como `ERROR_INTERNO`.
- Nunca se exponen trazas, URL internas ni la respuesta cruda de un servicio.
- `X-Correlation-Id`: si llega con un formato válido (`[A-Za-z0-9-]{1,64}`) se conserva; si no, se genera un UUID. Se envía en cada llamada a los microservicios y se devuelve en toda respuesta (RNF-22).
- Logs estructurados en JSON: un registro por consulta (`idCorrelacion`, `operacion`, `estado`, `duracionMs`, `cantidadLlamadas`, `cantidadErrores` y `sub`) y uno por cada llamada fallida a un servicio.
- Endpoint `/salud` con liveness y readiness. La readiness **no** depende de los microservicios ni de Keycloak (RNF-08).

## 8. Calidad

- Toda regla de las secciones 4 a 7 tiene al menos un test de integración con el gateway y Keycloak simulados.
- La tabla de permisos de la spec se prueba campo por campo, con cada rol.
- Cobertura mínima: 80 % de líneas de `src`. El pipeline falla si baja.
- Ninguna tarea se da por terminada con tests fallando.

## 9. Simplicidad

- No se construye nada que no esté en una spec. Un campo se agrega al esquema porque una pantalla de React lo necesita.
- Cada dependencia nueva se justifica en el plan.
- Nada de capas, directivas ni configuraciones "por si acaso".

## 10. Convenciones

- Se adopta completa la sección «Convenciones» común de los microservicios: nombres en español sin tildes ni ñ, Conventional Commits, fechas ISO 8601 UTC, decimales como texto y las excepciones en inglés que esa sección enumera.
- Tipos, enumeraciones y escalares del esquema en PascalCase; campos y argumentos en camelCase; valores de enumeraciones en mayúsculas con guion bajo. Términos impuestos por GraphQL (`Query`, `errors`, `extensions`) quedan en inglés.
- El pipeline vive en `.github/workflows/graphql-server.yml`, en la raíz, y se filtra por `servicios/graphql-server/**` (RNF-20).
- El servidor se levanta en local con Docker Compose, perfil `graphql` (RNF-19).

### Glosario de este servicio

| Concepto | Archivo / tipo | Variable de entorno |
|---|---|---|
| Esquema | `esquema.graphql` | — |
| Ruta pública | `/api/graphql` (a través del gateway) | — |
| Validación del token | `seguridad/` | `KEYCLOAK_JWKS_URI`, `KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE` |
| Cuenta de servicio | `fuentes/` | `KEYCLOAK_TOKEN_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET` |
| Acceso a los microservicios | `fuentes/` | `API_GATEWAY_URL` |
| Tiempo límite de cada llamada y plazo de la consulta | `fuentes/` | `GRAPHQL_TIEMPO_LIMITE_LLAMADA_MS`, `GRAPHQL_PLAZO_CONSULTA_MS` |
| Escalares | `Decimal`, `Fecha`, `FechaHora` | — |

| Código de error | Dónde |
|---|---|
| `NO_AUTENTICADO` (401), `SIN_PERMISO` (403), `AUTENTICACION_NO_DISPONIBLE` (503), `ERROR_INTERNO` (500) | Respuesta HTTP |
| `SIN_PERMISO`, `DATOS_INVALIDOS`, `DEPENDENCIA_NO_DISPONIBLE`, `CONSULTA_DEMASIADO_COMPLEJA`, `ERROR_INTERNO` | `extensions.codigo` de un error de campo |

## Enmiendas

- Versión: 1.0.0 (2026-11-06)
- Cambiar una regla requiere actualizar este documento, registrar el motivo y subir la versión:
  - MAJOR: se elimina o redefine una regla.
  - MINOR: se agrega una regla.
  - PATCH: aclaraciones de redacción sin cambio de significado.

| Versión | Fecha | Motivo |
|---|---|---|
| 1.0.0 | 2026-11-06 | Versión inicial. Solo consultas; las operaciones de IA van por REST. Acceso de React a través del gateway (`/api/graphql`). Cuenta de servicio hacia los microservicios, con permisos por campo que nunca superan los del usuario. Plazo total por consulta. CORS solo en el gateway, salvo Apollo Sandbox fuera de producción. |
