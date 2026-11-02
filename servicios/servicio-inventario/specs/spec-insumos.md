# Insumos — `servicio-inventario`

| Campo | Valor |
|---|---|
| Servicio | `servicio-inventario` |
| Archivo | `specs/spec-insumos.md` |
| Estado | Spec en borrador (2026-11-02) · Plan y tareas en borrador |
| Constitución | v2.8.0 |
| Trazabilidad | CU-06 (prioridad alta) · RF-07 · RN-04, RN-14, RN-15, RN-16 · RNF-05 |
| Depende de | — (incluye la Fase 0: base del servicio) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Escenarios de usuario y pruebas

### Historia 1 — Registrar un insumo (Prioridad: P1)

Como administrador, quiero registrar los insumos agrícolas con su categoría, unidad, nivel mínimo y costo unitario, para controlar su stock y calcular el costo de las labores.

**Por qué esta prioridad:** sin insumos no hay movimientos, alertas ni Saga. Es la base de todo el servicio.

**Prueba independiente:** se crea un insumo y se consulta; entrega valor por sí sola como catálogo.

**Escenarios de aceptación:**

1. **Dado** un administrador autenticado, **cuando** registra el insumo "Urea 46 %", categoría `FERTILIZANTE`, unidad `KILOGRAMO`, nivel mínimo `"50"`, costo unitario `"4.85"` y stock inicial `"500"`, **entonces** el insumo se crea con un UUID, stock `"500.000"`, y existe un movimiento `ENTRADA` de 500 kg con motivo "Stock inicial".
2. **Dado** el mismo registro sin `stockInicial`, **entonces** el insumo se crea con stock `"0.000"` y sin movimientos.
3. **Dado** un insumo con unidad `UNIDAD`, **cuando** se envía stock inicial `"10.5"` o nivel mínimo `"2.5"`, **entonces** se rechaza con `422 CANTIDAD_INVALIDA` y no se crea nada.
4. **Dado** un costo unitario `"-1"`, **entonces** se rechaza con `422 COSTO_UNITARIO_INVALIDO`; con `"0"` se acepta (insumo donado).
5. **Dado** que existe "Urea 46 %", **cuando** se registra "urea 46 %", **entonces** se rechaza con `409 NOMBRE_INSUMO_DUPLICADO`.
6. **Dado** un usuario `gerencia` o `tecnico_campo`, **cuando** intenta registrar un insumo, **entonces** recibe `403 SIN_PERMISO`.

### Historia 2 — Consultar insumos (Prioridad: P1)

Como administrador o gerente, quiero ver el catálogo de insumos con su stock y costo; como técnico de campo, quiero ver los insumos disponibles para registrar las labores, también sin conexión.

**Por qué esta prioridad:** el técnico de campo necesita el catálogo para registrar labores con insumos (`ConsumoInsumo` en `servicio-operaciones`).

**Prueba independiente:** con insumos cargados, se lista y se consulta uno con cada rol.

**Escenarios de aceptación:**

1. **Dado** 30 insumos, **cuando** un administrador pide el listado sin parámetros, **entonces** recibe los 20 primeros ordenados por nombre, con el total.
2. **Dado** el filtro `categoria=SEMILLA` y el texto `maiz`, **entonces** solo recibe las semillas cuyo nombre contiene "maiz", sin distinguir mayúsculas.
3. **Dado** el filtro `soloConStock=true`, **entonces** solo recibe insumos con stock mayor a 0.
4. **Dado** un usuario que solo tiene el rol `tecnico_campo`, **cuando** lista o consulta un insumo, **entonces** recibe `id`, `nombre`, `categoria`, `unidad` y `stock`, sin `costoUnitario`, `nivelMinimo` ni `version`.
5. **Dado** un usuario con `tecnico_campo` y `gerencia`, **entonces** recibe la vista completa.
6. **Dado** la cuenta de servicio con `lectura_inventario` (`servicio-ia`, GraphQL, n8n), **entonces** recibe la vista completa, y un `POST` o `PUT` responde `403 SIN_PERMISO` (RN-14).
7. **Dado** un ID inexistente, **entonces** recibe `404 INSUMO_NO_ENCONTRADO`.

### Historia 3 — Modificar un insumo (Prioridad: P2)

Como administrador, quiero corregir el nombre, la categoría, el nivel mínimo, el costo unitario o la descripción de un insumo, para mantener el catálogo al día.

**Por qué esta prioridad:** corrige errores de carga y actualiza precios, pero el servicio funciona sin ella.

**Prueba independiente:** se modifica un insumo y se verifica el cambio y su auditoría.

**Escenarios de aceptación:**

1. **Dado** un insumo con costo `"4.85"`, **cuando** el administrador lo cambia a `"5.10"`, **entonces** el insumo queda con `"5.1000"`, `version` aumenta en 1 y se registra la auditoría `MODIFICAR`.
2. **Dado** un insumo sin movimientos, **cuando** se cambia su unidad de `KILOGRAMO` a `LITRO`, **entonces** se acepta.
3. **Dado** un insumo con movimientos, **cuando** se cambia su unidad, **entonces** se rechaza con `422 UNIDAD_NO_MODIFICABLE`.
4. **Dado** que el insumo cambió desde que se leyó (otra edición), **cuando** se envía una `version` anterior, **entonces** se rechaza con `409 CONFLICTO_CONCURRENCIA`.
5. **Dado** que una labor descontó stock del insumo entre la lectura y el `PUT`, **entonces** el `PUT` se acepta: los movimientos no cambian `version`.
6. **Dado** un `PUT` con el campo `stock`, **entonces** se rechaza con `400 DATOS_INVALIDOS`: el stock solo cambia mediante movimientos.

### Casos borde

- Cantidades o costo con más decimales de los admitidos (`"1.2345"` de stock, `"1.23456"` de costo): `400 DATOS_INVALIDOS`.
- Decimales enviados como número JSON (`4.85` en lugar de `"4.85"`): `400 DATOS_INVALIDOS`.
- Nivel mínimo negativo: `422 NIVEL_MINIMO_INVALIDO`. Stock inicial negativo: `422 CANTIDAD_INVALIDA`.
- Nombre con espacios al inicio o al final: se recorta antes de validar unicidad y longitud.
- Dos creaciones simultáneas con el mismo nombre: una se crea y la otra recibe `409 NOMBRE_INSUMO_DUPLICADO`.
- Cambiar la unidad a `UNIDAD` con un nivel mínimo decimal: `422 CANTIDAD_INVALIDA`.

## 1.2 Requisitos

### Requisitos funcionales

- **RQ-INS-01**: El sistema debe permitir registrar un insumo con:
  - `nombre`: obligatorio, de 1 a 100 caracteres, único sin distinguir mayúsculas.
  - `categoria`: obligatoria, `SEMILLA`, `FERTILIZANTE` o `FITOSANITARIO`.
  - `unidad`: obligatoria, `KILOGRAMO`, `LITRO` o `UNIDAD`.
  - `nivelMinimo`: obligatorio, decimal ≥ 0, hasta 3 decimales (entero con `UNIDAD`).
  - `costoUnitario`: obligatorio, decimal ≥ 0, hasta 4 decimales, en `BOB`.
  - `stockInicial`: opcional, decimal ≥ 0, hasta 3 decimales (entero con `UNIDAD`); por defecto 0.
  - `descripcion`: opcional, hasta 500 caracteres.
- **RQ-INS-02**: Si `stockInicial` es mayor a 0, se crea en la misma transacción un movimiento `ENTRADA` por esa cantidad con motivo "Stock inicial" (constitución §3). Ese movimiento sigue las reglas de `spec-movimientos.md`.
- **RQ-INS-03**: Las reglas de rango (≥ 0, enteros con `UNIDAD`) se validan en el dominio y responden `422` con `CANTIDAD_INVALIDA`, `NIVEL_MINIMO_INVALIDO` o `COSTO_UNITARIO_INVALIDO`.
- **RQ-INS-04**: Un nombre repetido responde `409 NOMBRE_INSUMO_DUPLICADO`.
- **RQ-INS-05**: El sistema debe permitir modificar `nombre`, `categoria`, `unidad`, `nivelMinimo`, `costoUnitario` y `descripcion`, con las reglas de RQ-INS-01 y la `version` leída. `stock` no es modificable.
- **RQ-INS-06**: La unidad no cambia si el insumo tiene al menos un movimiento: `422 UNIDAD_NO_MODIFICABLE`.
- **RQ-INS-07**: Cambiar el costo unitario no altera los movimientos ya registrados ni las respuestas de Sagas ya procesadas (cada movimiento guarda el costo unitario vigente).
- **RQ-INS-08**: El sistema debe listar insumos paginados, ordenados por nombre, con filtros opcionales `nombre` (contenido, sin distinguir mayúsculas), `categoria` y `soloConStock`.
- **RQ-INS-09**: El sistema debe devolver el detalle de un insumo por ID, o `404 INSUMO_NO_ENCONTRADO`.
- **RQ-INS-10**: Vista según roles:
  - Completa (`administrador`, `gerencia`, `lectura_inventario`): todos los campos.
  - Reducida (solo `tecnico_campo`): `id`, `nombre`, `categoria`, `unidad`, `stock`.
- **RQ-INS-11**: Toda creación y modificación genera un registro de auditoría (usuario, acción, fecha y entidad).
- **RQ-INS-12**: Esta versión no incluye eliminación de insumos.

### Entidades clave

- **Insumo**: `id` (UUID), `nombre`, `categoria`, `unidad`, `stock`, `nivelMinimo`, `costoUnitario`, `descripcion`, `tieneMovimientos`, `fechaUltimaAlerta` (la usa `spec-stock-bajo.md`), `version`, `fechaCreacion`, `fechaActualizacion`.
- **Cantidad** (objeto de valor): decimal ≥ 0 con hasta 3 decimales, entero si la unidad es `UNIDAD`.
- **Dinero** (objeto de valor): decimal ≥ 0 en `BOB`.

## 1.3 Permisos

| Operación | Roles |
|---|---|
| Registrar y modificar | `administrador` |
| Listar y ver detalle (vista completa) | `administrador`, `gerencia`, `lectura_inventario` |
| Listar y ver detalle (vista reducida) | `tecnico_campo` |

## 1.4 Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Formato incorrecto, campo obligatorio ausente, campo no permitido, longitud o decimales excedidos, decimal como número JSON |
| 404 | `INSUMO_NO_ENCONTRADO` | El ID no existe |
| 409 | `NOMBRE_INSUMO_DUPLICADO` | El nombre ya está en uso |
| 409 | `CONFLICTO_CONCURRENCIA` | El insumo cambió desde que se leyó |
| 422 | `CANTIDAD_INVALIDA` | Stock inicial negativo, o decimal con unidad `UNIDAD` |
| 422 | `NIVEL_MINIMO_INVALIDO` | Nivel mínimo negativo |
| 422 | `COSTO_UNITARIO_INVALIDO` | Costo unitario negativo |
| 422 | `UNIDAD_NO_MODIFICABLE` | Cambio de unidad con movimientos registrados |

## 1.5 Criterios de éxito

- **CE-INS-01**: Ningún insumo queda con stock distinto de la suma de sus movimientos (verificado tras crear con y sin stock inicial).
- **CE-INS-02**: Listado y detalle responden en menos de 3 s con 1.000 insumos cargados (RNF-05).
- **CE-INS-03**: La vista reducida nunca incluye `costoUnitario` (verificado en tests de integración con cada endpoint de lectura).
- **CE-INS-04**: Toda creación y modificación tiene su registro de auditoría.

## 1.6 Supuestos

- El costo unitario es el precio de reposición vigente que fija el administrador; no se calcula promedio ponderado con las entradas.
- La app Flutter descarga el catálogo con la vista reducida y lo guarda para trabajar sin conexión; la sincronización de labores la resuelve `servicio-operaciones`.

## 1.7 Aclaraciones

- **AC-01** — Resuelta (constitución v2.6.0): `tecnico_campo` lee insumos sin costo unitario ni otros datos económicos. El nivel mínimo se considera dato de gestión y tampoco se incluye.
- **AC-02** — Resuelta (constitución v2.7.0): n8n tiene `lectura_inventario` para consultar el insumo antes de enviar la alerta.

## 1.8 Fuera de alcance

- Eliminación o desactivación de insumos.
- Proveedores, órdenes de compra, lotes y vencimientos.
- Costo promedio ponderado.

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución. Sin dependencias fuera del stack de la constitución y de D-13 del README.

**Documentos que debe tener a mano quien implemente:** la constitución de inventario v2.8.0 (`servicios/servicio-inventario/Constitucion.md`), `specs/README.md` (decisiones transversales) y este archivo.

## 2.1 Fase 0 — Base del servicio

Se construye una sola vez, con esta funcionalidad, y la reutilizan todas las demás.

### Dependencias (`package.json`)

| Dependencia | Para qué |
|---|---|
| `@nestjs/core`, `@nestjs/common`, `@nestjs/platform-express` 11 | Base |
| `@nestjs/swagger` | OpenAPI (constitución §2) |
| `class-validator`, `class-transformer` | Validación de DTO (constitución §2) |
| `mongoose` 8 | Persistencia (sin `@nestjs/mongoose`: la conexión se crea en un proveedor propio de ~10 líneas) |
| `decimal.js` | Aritmética decimal (constitución §4) |
| `jose` | Validación del JWT con JWKS, `iss`, `aud` y `exp` en una sola llamada |
| Dev: `typescript`, `@nestjs/cli`, `@nestjs/testing`, `jest`, `ts-jest`, `supertest`, `@testcontainers/mongodb`, `eslint`, `prettier` | Build, tests y estilo (eslint y prettier vienen con la plantilla de Nest) |

`amqplib` y `amqp-connection-manager` se agregan recién en `spec-stock-bajo.md`, la primera funcionalidad que usa RabbitMQ.

### Configuración

- `config/validacion-entorno.ts`: lee y valida al arrancar `PORT`, `MONGODB_URI`, `KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URI` y `KEYCLOAK_AUDIENCE` (README D-14). Si falta una, lanza un error y el proceso termina.
- `main.ts`:
  - `app.setGlobalPrefix('api/inventario/v1', { exclude: ['salud', 'salud/liveness', 'salud/readiness'] })`.
  - `ValidationPipe` global con `whitelist`, `forbidNonWhitelisted` y `transform`.
  - Logger: subclase `LoggerJson` de `ConsoleLogger` con `json: true`, que agrega `idCorrelacion` desde el contexto de la solicitud.
  - Swagger en `/api-docs` (UI) y `/api-docs-json`, fuera del prefijo y sin token.
- `tsconfig.json` con `strict: true`.

### Conexión a MongoDB y migraciones

- `ProveedorConexionMongo` (en `adapters/outbound/persistence`) crea la conexión con `mongoose.createConnection(MONGODB_URI, { autoIndex: false })`.
- **Ejecutor de migraciones** (`migrations/ejecutor.ts`, ~50 líneas): al arrancar, antes de escuchar, lee los archivos `migrations/NNN-*.ts` en orden, ejecuta `subir(db)` de los que no están en la colección `migraciones` y registra cada uno (`_id` = nombre, `fecha`). Los tests de integración ejecutan el mismo ejecutor.
- **Unidad de trabajo** (`UnidadTrabajo`, puerto en `application/ports`): `ejecutar(fn)` abre una sesión y llama a `session.withTransaction(fn)`, que reintenta ante errores transitorios. La sesión activa viaja en un `AsyncLocalStorage` del adaptador; los repositorios Mongo la toman de ahí, así el dominio y los casos de uso no conocen la sesión.

### Seguridad

- **`JwtGuardia`** (guardia global): lee `Authorization: Bearer`, valida con `jwtVerify(token, jwks, { issuer, audience })` de `jose` y deja en la solicitud `sub` y los roles de `realm_access.roles`. Sin token o con token inválido: `401 NO_AUTENTICADO`. Las rutas marcadas con `@Publica()` (salud) no lo exigen.
- **JWKS:** proveedor `CONJUNTO_CLAVES` = `createRemoteJWKSet(KEYCLOAK_JWKS_URI)`. Las claves se descargan por la red interna (`keycloak:8080`) y el emisor solo se compara con `iss` (`localhost:8180`), igual que en `servicio-gestion`.
- **`RolesGuardia`** y decorador `@Roles(...)`: si el usuario no tiene ninguno de los roles, `403 SIN_PERMISO`.
- **Roles:**

  | Rol de realm | Quién lo tiene |
  |---|---|
  | `administrador`, `gerencia`, `tecnico_campo` | Usuarios |
  | `lectura_inventario` | Cuentas de servicio de `servicio-ia`, GraphQL y n8n |

- Los tests generan un par de claves con `jose`, firman sus propios tokens y reemplazan `CONJUNTO_CLAVES` por `createLocalJWKSet`. Así se prueban de verdad firma, `iss`, `aud` y `exp`, sin levantar Keycloak.

### Errores

- **`ErrorDominio`** (en `domain/shared`) lleva `codigo`, `mensaje` y un `tipo` (`NO_ENCONTRADO`, `CONFLICTO` o `REGLA_NEGOCIO`). El dominio no conoce HTTP.
- **`FiltroExcepcionesHttp`** (filtro global) responde siempre `{ codigo, mensaje, detalles, idCorrelacion }`:

  | Origen | HTTP | Código |
  |---|---|---|
  | `BadRequestException` del `ValidationPipe` o JSON mal formado | 400 | `DATOS_INVALIDOS`, con un detalle por campo |
  | `UnauthorizedException` de `JwtGuardia` | 401 | `NO_AUTENTICADO` |
  | `ForbiddenException` de `RolesGuardia` | 403 | `SIN_PERMISO` |
  | `ErrorDominio` tipo `NO_ENCONTRADO` | 404 | El de la excepción |
  | `NotFoundException` de Nest (ruta inexistente) | 404 | `RECURSO_NO_ENCONTRADO` |
  | `ErrorDominio` tipo `CONFLICTO` | 409 | El de la excepción |
  | `ErrorDominio` tipo `REGLA_NEGOCIO` | 422 | El de la excepción |
  | Cualquier otra | 500 | `ERROR_INTERNO`, sin exponer detalles; el error completo va al log |

### Correlación y logs

- **`IdCorrelacionMiddleware`**: toma `X-Correlation-Id` o genera un UUID, lo guarda en un `AsyncLocalStorage` de contexto y lo devuelve en el header de la respuesta. Se registra antes de las guardias, para que los 401 y 403 también lo incluyan.
- Los logs no incluyen tokens ni datos personales; solo el `sub`.

### Auditoría

- **Puerto** `RegistroAuditoria` en `application/ports`: `registrar({ actor, accion, entidad, idEntidad })`.
- **Implementación** `RegistroAuditoriaMongo`: inserta en `registros_auditoria` (`_id`, `actor`, `accion`, `entidad`, `id_entidad`, `id_correlacion`, `fecha`) dentro de la sesión activa.
- El actor lo pasa el caso de uso: el `sub` del token en REST, el `origen` del mensaje en la Saga.
- **Acciones:** `CREAR`, `MODIFICAR`, `REGISTRAR_MOVIMIENTO`, `DESCONTAR_INSUMOS_SAGA` y `RESTAURAR_INSUMOS_SAGA`.

**`001-crear-indices-auditoria.ts`**: índice `{ entidad: 1, id_entidad: 1 }`.

### Reloj

Puerto `Reloj` (`ahora(): Date`) con implementación del sistema; los tests de la regla de 24 h (`spec-stock-bajo.md`) usan uno fijo.

### Formato JSON

- Los decimales salen como texto con escala fija: cantidades con 3 decimales, costo unitario con 4 (README D-01, D-02).
- En la entrada, todo decimal es `@IsString()` + `@Matches(...)`. Un número JSON falla `@IsString()` y termina en `400 DATOS_INVALIDOS` (README D-09).
- Fechas como `toISOString()` (UTC).

### Paginación (común a todos los listados)

- DTO `ConsultaPaginada`: `pagina` (`@IsInt() @Min(0)`, por defecto 0) y `tamanio` (`@IsInt() @Min(1) @Max(100)`, por defecto 20).
- Respuesta `{ items, pagina, tamanio, total }`.

### Salud

`SaludControlador` propio (sin `@nestjs/terminus`), con `@Publica()`:

- `GET /salud/liveness`: `200 { estado: "UP" }` si el proceso responde.
- `GET /salud/readiness`: `db.admin().ping()` a MongoDB (y RabbitMQ desde `spec-stock-bajo.md`). `200` si todo responde; `503` con el detalle si algo falla.
- `GET /salud`: igual que readiness.

### Empaquetado y pipeline

- **`Dockerfile`** multi-etapa sobre `node:24-alpine`: `npm ci` y `npm run build`; la imagen final solo lleva `dist`, `node_modules` de producción y `migrations` compiladas, y corre con el usuario `node`.
- **`.github/workflows/servicio-inventario.yml`** (en la raíz del repositorio, filtrado por `servicios/servicio-inventario/**`): `npm ci`, `npm run lint`, `npm run build`, `npm test -- --coverage` y construcción de la imagen.
- **Jest:** un solo proyecto que corre unitarios e integración; `coverageThreshold` de 80 % de líneas en `src/domain/**` y `src/application/**`.
- Docker Compose arranca el servicio con `npm run start:dev`; aquí solo se garantiza que la imagen arranca con las variables de README D-14.

## 2.2 Endpoints

Prefijo: `/api/inventario/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /insumos` | `administrador` | `201` + `Location` + insumo | 400, 401, 403, 409 `NOMBRE_INSUMO_DUPLICADO`, 422 |
| `GET /insumos?nombre=&categoria=&soloConStock=&pagina=&tamanio=` | `administrador`, `gerencia`, `lectura_inventario`, `tecnico_campo` | `200` + página | 400, 401, 403 |
| `GET /insumos/{id}` | Igual que el listado | `200` + insumo | 401, 403, 404 `INSUMO_NO_ENCONTRADO` |
| `PUT /insumos/{id}` | `administrador` | `200` + insumo | 400, 401, 403, 404, 409 `NOMBRE_INSUMO_DUPLICADO` o `CONFLICTO_CONCURRENCIA`, 422 |

**Solicitud de creación:**

```json
{
  "nombre": "Urea 46 %",
  "categoria": "FERTILIZANTE",
  "unidad": "KILOGRAMO",
  "nivelMinimo": "50",
  "costoUnitario": "4.85",
  "stockInicial": "500",
  "descripcion": "Bolsa de 50 kg"
}
```

**Solicitud de modificación:** los mismos campos, sin `stockInicial` y con `version`.

**Respuesta de insumo (vista completa):**

```json
{
  "id": "0b6f…",
  "nombre": "Urea 46 %",
  "categoria": "FERTILIZANTE",
  "unidad": "KILOGRAMO",
  "stock": "500.000",
  "nivelMinimo": "50.000",
  "costoUnitario": "4.8500",
  "descripcion": "Bolsa de 50 kg",
  "stockBajo": false,
  "version": 0,
  "fechaCreacion": "2026-11-02T14:00:00Z",
  "fechaActualizacion": "2026-11-02T14:00:00Z"
}
```

**Respuesta de insumo (vista reducida):** `id`, `nombre`, `categoria`, `unidad`, `stock`.

**Validaciones del DTO** (responden `400 DATOS_INVALIDOS`):

| Campo | Regla |
|---|---|
| `nombre` | `@IsString()`, recortado, longitud 1 a 100 |
| `categoria` | `@IsEnum(CategoriaInsumo)` |
| `unidad` | `@IsEnum(UnidadMedida)` |
| `nivelMinimo`, `stockInicial` | `@IsString()`, `@Matches(/^-?\d{1,12}(\.\d{1,3})?$/)` |
| `costoUnitario` | `@IsString()`, `@Matches(/^-?\d{1,12}(\.\d{1,4})?$/)` |
| `descripcion` | `@IsOptional()`, `@MaxLength(500)` |
| `version` (solo en `PUT`) | `@IsInt()`, `@Min(0)` |

El signo negativo pasa el DTO a propósito: el dominio lo rechaza con el `422` correspondiente, como exige RQ-INS-03.

## 2.3 Modelo de datos

Colección `insumos`:

| Campo | Tipo | Nota |
|---|---|---|
| `_id` | `String` (UUID) | |
| `nombre` | `String` | |
| `nombre_normalizado` | `String` | `nombre` recortado y en minúsculas |
| `categoria` | `String` | Enumeración |
| `unidad` | `String` | Enumeración |
| `stock` | `Decimal128` | Solo lo cambian los movimientos |
| `nivel_minimo` | `Decimal128` | |
| `costo_unitario` | `Decimal128` | |
| `descripcion` | `String` | Opcional |
| `tiene_movimientos` | `Boolean` | `true` desde el primer movimiento |
| `fecha_ultima_alerta` | `Date` | `null` hasta la primera alerta (`spec-stock-bajo.md`) |
| `reserva_alerta_hasta` | `Date` | `null`; lo usa `spec-stock-bajo.md` |
| `version` | `Number` | Solo la incrementa `PUT` |
| `fecha_creacion`, `fecha_actualizacion` | `Date` | |

**`002-crear-indices-insumos.ts`**: índice único `{ nombre_normalizado: 1 }` e índice `{ categoria: 1, nombre_normalizado: 1 }`.

- El índice único garantiza la unicidad también ante creaciones simultáneas; el error `11000` se traduce a `NOMBRE_INSUMO_DUPLICADO`.
- El filtro por `nombre` usa una expresión regular sobre `nombre_normalizado` con el texto escapado.

## 2.4 Diseño por capas

| Capa | Archivo | Responsabilidad |
|---|---|---|
| `domain/shared` | `cantidad.vo.ts` | `Cantidad.de(texto, unidad)`: ≥ 0, hasta 3 decimales, entero con `UNIDAD`; operaciones `sumar`, `restar`, `esMenorOIgualQue` con `decimal.js` |
| `domain/shared` | `dinero.vo.ts` | `Dinero`: ≥ 0, `multiplicar(cantidad)`, `redondearA2()` mitad hacia arriba |
| `domain/shared` | `error-dominio.ts` | Error con código y tipo |
| `domain/supply` | `insumo.entidad.ts`, `categoria-insumo.enum.ts`, `unidad-medida.enum.ts` | `Insumo.crear(...)` y `actualizar(...)`: recortan el nombre, validan rangos y bloquean el cambio de unidad si `tieneMovimientos` |
| `application/ports` | `repositorio-insumo.puerto.ts` | `guardarNuevo`, `actualizarSiVersion(insumo, version)`, `buscarPorId`, `listar(filtros, pagina, tamanio)` |
| `application/use-cases` | `crear-insumo.caso-uso.ts` | En una transacción: crea el insumo, registra el movimiento de stock inicial si corresponde (usa el caso de uso de `spec-movimientos.md`) y audita `CREAR` |
| `application/use-cases` | `actualizar-insumo.caso-uso.ts` | Busca (o 404), aplica `actualizar`, guarda si la `version` coincide (si no, `CONFLICTO_CONCURRENCIA`) y audita `MODIFICAR` |
| `application/use-cases` | `consultar-insumos.caso-uso.ts` | Detalle y listado |
| `adapters/outbound/persistence` | `insumo.esquema.ts`, `mappers/insumo.mapper.ts`, `repositorio-insumo.mongo.ts` | Esquema, mapeo `Decimal128` ↔ `Decimal`, traducción del error `11000` |
| `adapters/inbound/http` | `insumos.controlador.ts`, `dto/` | Traduce HTTP ↔ caso de uso; elige la vista completa o reducida según los roles |

**Stock inicial (RQ-INS-02):** el movimiento se crea en la misma transacción. Hasta que exista `spec-movimientos.md`, la tarea T12 implementa solo la creación sin stock inicial; T03 de `spec-movimientos.md` completa el escenario 1 de la Historia 1.

**Concurrencia (RQ-INS-05):** `updateOne({ _id, version }, { $set: {...}, $inc: { version: 1 } })`; si no modifica nada y el insumo existe, `CONFLICTO_CONCURRENCIA`. Los movimientos usan `$inc` sobre `stock` sin tocar `version` (README D-05).

## 2.5 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `cantidad.vo.spec.ts` | Negativos, más de 3 decimales, decimales con `UNIDAD`, operaciones exactas (`0.1 + 0.2 = 0.3`) |
| Unitario | `dinero.vo.spec.ts` | Negativos, multiplicación exacta, redondeo mitad hacia arriba (`0.125 → 0.13`, `0.124 → 0.12`) |
| Unitario | `insumo.entidad.spec.ts` | Recorte del nombre, rangos, cambio de unidad con y sin movimientos |
| Unitario | `actualizar-insumo.caso-uso.spec.ts` | 404, `CONFLICTO_CONCURRENCIA`, auditoría `MODIFICAR` (dobles escritos a mano) |
| Integración | `insumos.controlador.int-spec.ts` | Historias 1 a 3 y casos borde de formato, con verificación de `registros_auditoria` |
| Integración | `insumos-vistas.int-spec.ts` | Vista reducida para `tecnico_campo` en listado y detalle; vista completa con roles combinados y con `lectura_inventario` (CE-INS-03) |
| Integración | `insumos-concurrencia.int-spec.ts` | Dos creaciones con el mismo nombre → `201` y `409`; dos `PUT` con la misma versión → el segundo `409` |
| Integración | `insumos-rendimiento.int-spec.ts` | 1.000 insumos, listado y detalle en menos de 3 s (CE-INS-02) |
| Integración | `seguridad.int-spec.ts` | Sin token → 401; firma, `iss`, `aud` o `exp` inválidos → 401; rol sin permiso → 403; `/salud` y `/api-docs-json` sin token; `X-Correlation-Id` en 401 y 403 |
| Integración | `errores.int-spec.ts` | Formato común en 400, 404 de ruta inexistente y 500 |

Los tests de integración levantan MongoDB con `@testcontainers/mongodb` (`mongo:8.0`, replica set de un nodo), ejecutan las migraciones y arrancan la app con `Test.createTestingModule`.

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

## Fase 0 — Base del servicio

- [ ] **T01** — Crear el proyecto NestJS (`package.json`, `tsconfig.json` con `strict`, `main.ts`, `app.module.ts`) con las dependencias de 2.1 y las carpetas de la constitución. *Hecho cuando:* `npm run build` compila.
- [ ] **T02** — Implementar `validacion-entorno.ts`, `ProveedorConexionMongo`, el ejecutor de migraciones y `UnidadTrabajo`. *Hecho cuando:* la app arranca contra el MongoDB de Docker Compose y registra las migraciones en `migraciones`.
- [ ] **T03** — Implementar `SaludControlador`. *Hecho cuando:* `/salud`, `/salud/liveness` y `/salud/readiness` responden sin token, y readiness responde `503` si MongoDB no está.
- [ ] **T04** — Implementar `JwtGuardia`, `RolesGuardia`, `@Roles`, `@Publica` y el soporte de tokens de prueba. *Hecho cuando:* pasa `seguridad.int-spec.ts`.
- [ ] **T05** [P] — Implementar `ErrorDominio` y `FiltroExcepcionesHttp`. *Hecho cuando:* pasa `errores.int-spec.ts`.
- [ ] **T06** [P] — Implementar `IdCorrelacionMiddleware` y `LoggerJson`. *Hecho cuando:* la respuesta devuelve el `X-Correlation-Id` recibido o uno generado, y aparece en los logs.
- [ ] **T07** — Crear `001-crear-indices-auditoria.ts` y `RegistroAuditoriaMongo`. *Hecho cuando:* un test de integración registra una auditoría dentro de una transacción y la lee con actor e `idCorrelacion`.
- [ ] **T08** [P] — Crear `ConsultaPaginada`, la respuesta paginada, `Reloj` y la configuración de Swagger.
- [ ] **T09** [P] — Escribir el `Dockerfile` y `.github/workflows/servicio-inventario.yml`, con el umbral de cobertura de Jest. *Hecho cuando:* el pipeline corre en verde y construye la imagen.

## Fase 1 — Insumos

- [ ] **T10** — Crear `Cantidad`, `Dinero`, `Insumo` y sus enumeraciones, con sus tests unitarios.
- [ ] **T11** — Crear `002-crear-indices-insumos.ts`, el esquema, el mapper y `RepositorioInsumoMongo`, con la traducción del error `11000`.
- [ ] **T12** — Implementar `CrearInsumoCasoUso` (sin stock inicial) y `POST /insumos`. *Hecho cuando:* pasan los escenarios 2 a 6 de la Historia 1, con auditoría.
- [ ] **T13** — Implementar `ConsultarInsumosCasoUso` y los dos `GET`, con las dos vistas. *Hecho cuando:* pasan la Historia 2 e `insumos-vistas.int-spec.ts`.
- [ ] **T14** — Implementar `ActualizarInsumoCasoUso` y `PUT /insumos/{id}`. *Hecho cuando:* pasan los escenarios 1, 2, 4 y 6 de la Historia 3 (el 3 y el 5 necesitan movimientos y se completan en `spec-movimientos.md`).
- [ ] **T15** — Escribir `insumos-concurrencia.int-spec.ts` y los casos borde de formato.
- [ ] **T16** [P] — Escribir `insumos-rendimiento.int-spec.ts` (CE-INS-02).
- [ ] **T17** — Documentar en OpenAPI los códigos de error de cada endpoint. *Hecho cuando:* `/api-docs-json` lista los cuatro endpoints con sus respuestas de error.
- [ ] **T18** — Verificación final: `npm test` en verde, cobertura ≥ 80 % en `domain` y `application`, y criterios CE-INS-01 a CE-INS-04 cubiertos por al menos un test.
