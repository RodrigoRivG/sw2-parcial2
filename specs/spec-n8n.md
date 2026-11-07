# Automatización con n8n — sistema

| Campo | Valor |
|---|---|
| Alcance | Todo el sistema, Módulo 8 (no pertenece a un microservicio) |
| Archivo | `specs/spec-n8n.md` |
| Estado | Fase 1 implementada (2026-11-07), salvo T08 (bloqueada por la app Flutter) · Fase 2 pendiente (opcional) |
| Referencias | `servicio-operaciones/specs/spec-labores.md` (listado de labores, RQ-LAB-14 a RQ-LAB-17), `servicio-operaciones/specs/spec-incidencias.md` (evento `IncidenciaRegistrada`, RQ-INC-07), `specs/spec-keycloak-realm.md` (cuenta de servicio `n8n`, RQ-KC-04) |
| Trazabilidad | Fase 1: CU-21, CU-22 · RF-30, RF-31 · RNF-03, RNF-19. Fase 2 (opcional): CU-20, CU-25 · RF-29, RF-34 |
| Depende de | `servicio-operaciones`, `api-gateway`, RabbitMQ y el realm `agro` (implementados). Para ver los avisos en un teléfono, la app Flutter (sin spec todavía). |

Contenido:

1. [Spec](#1-spec): qué deben hacer los flujos.
2. [Plan](#2-plan): cómo se construyen.
3. [Tareas](#3-tareas): en qué orden se implementan.

---

# 1. Spec

## Contexto

n8n es la plataforma de automatización del sistema (Módulo 8): ejecuta flujos que reaccionan a eventos o a un horario, consultan los microservicios a través del API Gateway y avisan a las personas. No tiene lógica de negocio ni datos propios.

**Decisión del 2026-11-07 (exigencia del docente):** los avisos se envían como **notificaciones push** a la app móvil, en lugar de correo. La app solo la instala el técnico de campo, así que el push es para él. El aviso de incidencias es inmediato, para poder demostrar la notificación en vivo durante la defensa. Se trabaja en dos fases:

| Fase | Contenido | Obligatoria |
|---|---|---|
| 1 | Push a los técnicos: aviso inmediato de incidencia registrada (RF-31) y recordatorio diario de labores programadas (RF-30) | Sí |
| 2 | Avisos por correo al administrador y a gerencia: stock bajo (RF-29), incidencias (RF-31) y reporte periódico (RF-34) | No: solo si hay tiempo |

**Diferencias intencionales con el documento de requisitos:**

- **Push en lugar de correo:** RF-30 y RF-31 piden avisos por correo. Aquí van por push, porque lo pide el docente.
- **Los avisos van a todos los técnicos:**
  - RF-30 dirige el recordatorio "al responsable", pero el responsable de una labor programada es el administrador que la programó, no un técnico (`spec-labores.md` RQ-LAB-04). Las labores programadas no se asignan a un técnico: cualquiera puede realizarlas (RQ-LAB-17). El aviso tiene que llegar a quienes pueden hacerlas.
  - RF-31 dirige el aviso de incidencias al administrador (proceso 3, Módulo 8). Aquí llega a los técnicos, que trabajan en las mismas parcelas. El correo al administrador queda en la fase 2.

**Contrato con la app Flutter** (lo implementa su spec):

- **Suscripción:** al iniciar sesión, un usuario con rol `tecnico_campo` se suscribe al tema de Firebase Cloud Messaging (FCM) `tecnicos`, y al cerrar sesión se da de baja.
- **Contenido de cada notificación:** `notification.title`, `notification.body` y estos `data`, todos como texto:

| `data.tipo` | Otros campos de `data` |
|---|---|
| `INCIDENCIA_REGISTRADA` | `idIncidencia`, `tipoIncidencia`, `idParcela` |
| `RECORDATORIO_LABORES` | `retrasadas`, `proximas`, `fecha` |

## 1.1 Escenarios de usuario y pruebas

### Historia 1 — Avisar al instante de una incidencia registrada (Prioridad: P1)

Como técnico de campo, quiero recibir en la app un aviso en cuanto alguien registra una incidencia, para enterarme de una plaga o enfermedad en las parcelas sin esperar (CU-22, RF-31).

**Por qué esta prioridad:** es el aviso que se puede demostrar en vivo, porque lo dispara una acción del propio técnico.

**Prueba independiente:** se registra una incidencia (o se publica el evento en el exchange `eventos`) y se comprueba en el historial de n8n que la ejecución terminó bien y que FCM devolvió el ID del mensaje.

**Escenarios de aceptación:**

1. **Dado** que un técnico registra una incidencia `PLAGA` desde Vue o Flutter, **cuando** operaciones publica el evento `operaciones.incidencia.registrada`, **entonces** n8n envía en segundos una notificación al tema `tecnicos` con título "Plaga registrada", cuerpo "<nombre de quien la registró>: <descripción, hasta 100 caracteres>" y `data` `{ tipo: "INCIDENCIA_REGISTRADA", idIncidencia, tipoIncidencia: "PLAGA", idParcela }`.
2. **Dado** una incidencia `PLAGA` o `ENFERMEDAD`, **entonces** la notificación sale con prioridad alta. Con `DANIO` u `OTRO`, sale con prioridad normal, y el título dice "Daño registrado" u "Otra incidencia registrada". Así se cumple "diferenciando prioridad por tipo" de RF-31.
3. **Dado** que n8n estaba apagado cuando se registró la incidencia, **cuando** vuelve a arrancar, **entonces** procesa el evento que quedó en su cola y envía el aviso. El evento no se pierde (constitución común de los servicios, Mensajería).
4. **Dado** que FCM rechaza el envío, **entonces** la ejecución queda como fallida en el historial de n8n y el mensaje se descarta. No hay reintentos (el trigger confirma el mensaje al recibirlo).

### Historia 2 — Recordar las labores programadas a los técnicos (Prioridad: P1)

Como técnico de campo, quiero recibir cada mañana en la app un aviso con las labores programadas que están retrasadas o que vencen hoy o mañana, para no olvidarlas (CU-21, RF-30).

**Prueba independiente:** con labores programadas en distintas fechas, se ejecuta el flujo y se comprueba que FCM aceptó el envío al tema `tecnicos` con los conteos correctos.

**Escenarios de aceptación:**

1. **Dado** dos labores `PROGRAMADA` con fecha anterior a hoy y tres con fecha de hoy o de mañana, **cuando** el flujo corre a las 07:00 (hora de Bolivia), **entonces** envía **una sola** notificación al tema `tecnicos`, con título "Labores programadas", cuerpo "2 retrasadas y 3 para hoy o mañana" y `data` `{ tipo: "RECORDATORIO_LABORES", retrasadas: "2", proximas: "3", fecha: "<hoy>" }`.
2. **Dado** que no hay labores retrasadas ni próximas, **entonces** no se envía nada.
3. **Dado** labores en otros estados (`PENDIENTE`, `CONFIRMADA`…), **entonces** no se cuentan: solo cuentan las `PROGRAMADA`.
4. **Dado** más de 100 labores en un grupo, **entonces** el flujo sigue el `siguienteCursor` de operaciones hasta contarlas todas.
5. **Dado** que operaciones, el gateway o Keycloak no responden, o que FCM rechaza el envío, **entonces** la ejecución queda como fallida en el historial de n8n, sin enviar nada, y el flujo vuelve a correr al día siguiente. No hay reintentos.
6. **Dado** la defensa, **cuando** se ejecuta el flujo a mano desde la interfaz de n8n, **entonces** el aviso llega en segundos.

### Historia 3 — Levantar n8n sin pasos manuales (Prioridad: P1)

Como desarrollador, quiero que `docker compose --profile n8n up` deje los flujos importados, con sus credenciales y activos, sin configurar nada en la interfaz de n8n (RNF-19).

**Escenarios de aceptación:**

1. **Dado** un volumen de n8n vacío y el archivo de la cuenta de servicio de Firebase en su lugar (2.3), **cuando** arranca el contenedor, **entonces** los dos flujos quedan importados y activos, con sus dos credenciales.
2. **Dado** que el contenedor se reinicia, **entonces** la importación se repite sin duplicar los flujos ni las credenciales.
3. **Dado** el repositorio, **entonces** no contiene secretos: ni el secreto del client de Keycloak, ni la clave de la cuenta de servicio de Firebase, ni la contraseña de RabbitMQ, ni la clave de cifrado de n8n (RNF-03).

### Historia 4 — Avisos por correo al administrador y a gerencia (Prioridad: P3, fase 2, opcional)

Como administrador o gerente, quiero recibir por correo los avisos que no me llegan por la app (RF-29, RF-31, RF-34).

**Escenarios de aceptación** (con un servidor de correo de desarrollo, Mailpit):

1. **Dado** el evento `inventario.stock.bajo` en el exchange `eventos`, **entonces** llega un correo al administrador con el insumo, su stock y su nivel mínimo. La regla de "uno cada 24 h" ya la aplica inventario.
2. **Dado** el evento `operaciones.incidencia.registrada`, **entonces**, además del push de la historia 1, llega un correo al administrador, marcado como prioritario si la incidencia es `PLAGA` o `ENFERMEDAD`.
3. **Dado** el horario semanal, **entonces** n8n pide un reporte a IA (`POST /api/ia/v1/reportes` con un plan fijo), espera el evento `ia.reporte.completado`, descarga el archivo y lo envía por correo a gerencia.

Los destinatarios se fijan por variable de entorno. Esta fase cierra la T07 pendiente de `servicio-inventario/specs/spec-stock-bajo.md` (contrato del evento de stock bajo).

### Casos borde

- **"Hoy" es la fecha UTC**, como en `servicio-operaciones` (README D-04). A las 07:00 de Bolivia (UTC−4) son las 11:00 UTC, así que la fecha coincide.
- **Una labor programada para hoy cuenta como próxima**, no como retrasada.
- **Ningún técnico suscrito al tema:** FCM acepta el envío igual. Los flujos no saben cuántos dispositivos lo reciben, y no les hace falta.
- **Quien registra la incidencia también recibe el aviso**, porque está suscrito al tema. El tema no permite excluir a nadie, y para la demostración sirve: basta un solo teléfono.
- **Evento repetido:** si operaciones republica un evento que ya había salido, el aviso puede llegar dos veces. Es aceptable: n8n no guarda los eventos procesados.
- **Evento con datos inválidos** (sin `datos.tipo`, por ejemplo): la ejecución falla, queda en el historial y el mensaje se descarta.
- **El token de la cuenta de servicio vence:** no pasa, porque `recordatorio-labores` pide un token nuevo en cada ejecución. El token de Google para FCM lo renueva la credencial de n8n.

## 1.2 Requisitos

- **RQ-N8N-01:** un flujo `incidencia-registrada` que consume el evento `operaciones.incidencia.registrada` desde una cola durable propia de n8n, enlazada al exchange `eventos`, y envía la notificación de la historia 1.
- **RQ-N8N-02:** un flujo `recordatorio-labores` con disparador diario a las 07:00 (`America/La_Paz`).
- **RQ-N8N-03:** `recordatorio-labores` obtiene, a través del gateway y con la cuenta de servicio `n8n`, las labores `PROGRAMADA` retrasadas (`fechaHasta` = ayer) y las próximas (`fechaDesde` = hoy, `fechaHasta` = mañana), recorriendo todas las páginas. Si alguno de los dos conteos es mayor que cero, envía la notificación de la historia 2; si no, no envía nada.
- **RQ-N8N-04:** las notificaciones se envían al tema `tecnicos` con la API HTTP v1 de FCM, con el contenido del contrato del Contexto.
- **RQ-N8N-05:** cada ejecución queda en el historial de n8n con la respuesta de FCM (`name`, el ID del mensaje) o con el error.
- **RQ-N8N-06:** el contenedor importa los flujos y sus credenciales al arrancar, de forma repetible, y deja los flujos activos.
- **RQ-N8N-07:** secretos solo por variables de entorno o archivos fuera del repositorio (RNF-03).
- **RQ-N8N-08 (fase 2):** flujos de la historia 4, con Mailpit en Docker Compose.

## 1.3 Criterios de éxito

- **CE-N8N-01:** tras registrar una incidencia (o publicar el evento en `eventos`), el historial de n8n muestra en segundos una ejecución exitosa de `incidencia-registrada` con un `name` de FCM.
- **CE-N8N-02:** con al menos una labor `PROGRAMADA` retrasada o próxima, ejecutar `recordatorio-labores` por CLI (2.8) termina con `status: success`, último nodo `fcm` y un `name` de FCM.
- **CE-N8N-03:** `git grep` no encuentra secretos en `docker/n8n/`.
- **CE-N8N-04 (cuando exista la app Flutter):** un teléfono con la app y un técnico conectado recibe los dos avisos. El de incidencias llega en segundos después de registrarla (demostración de la defensa).

## 1.4 Supuestos

- El proyecto de Firebase y su cuenta de servicio los crea el usuario en la consola de Firebase (T01). Sin ellos los flujos se ejecutan, pero fallan al enviar.
- La app Flutter implementa la suscripción al tema `tecnicos` (contrato del Contexto).
- El evento `IncidenciaRegistrada` lleva en `datos` `{ idIncidencia, tipo, descripcion, idParcela, idCampania, fechaObservacion, registradaPor: { id, nombre }, clasificacion }` dentro del sobre común (`spec-incidencias.md`, historia 3).
- En la nube, n8n corre en GCP con las mismas variables de entorno y se conecta a RabbitMQ (Amazon MQ) por AMQPS. El proyecto de Firebase es de GCP.

## 1.5 Aclaraciones

- **¿Por qué un tema y no un aviso por técnico?** Las labores programadas no tienen técnico asignado (Contexto) y una incidencia interesa a todos los que trabajan en el campo. Además, un tema evita guardar los tokens de los dispositivos: no hace falta un servicio nuevo ni cambiar ninguno.
- **¿Por qué el recordatorio es una sola notificación con conteos y no una por labor?** Para no llenar el teléfono de avisos: el detalle está en la app.
- **¿Por qué la cola es de n8n y no un webhook?** Así lo fija la constitución común de los servicios (v2.7.0): cada consumidor crea su propia cola enlazada al exchange `eventos`. Ningún servicio llama a un webhook de n8n, y un evento no se pierde si n8n está apagado.
- **Limitación conocida:** FCM no restringe quién se suscribe a un tema, así que cualquier instalación de la app podría recibir los avisos. Llevan un resumen de la incidencia o conteos, no datos sensibles, y es aceptable para el examen.
- **Acceso a variables de entorno desde los nodos:** n8n 2.x lo bloquea por defecto (`N8N_BLOCK_ENV_ACCESS_IN_NODE=true`). Se habilita para leer las URL (gateway, token de Keycloak y proyecto de Firebase) y el secreto del client `n8n`, que usa el nodo Code del recordatorio (D-N8N-08). El secreto no se ve en la interfaz ni en el repositorio. La clave de Firebase y la contraseña de RabbitMQ van en credenciales de n8n.

## 1.6 Fuera de alcance

- Push para el administrador o gerencia, y push en los micro frontends web (decisión del 2026-11-07).
- Guardar tokens de dispositivos o enviar avisos a un técnico en particular.
- Cambios en los microservicios.
- La suscripción al tema dentro de la app (spec de Flutter).
- Deduplicar eventos repetidos (casos borde).

---

# 2. Plan

Criterio general: lo mínimo que cumple la fase 1, sin cambiar nada de lo ya implementado. Todo lo de n8n vive en `docker/n8n/`, como el realm de Keycloak en `docker/keycloak/`. Versión fijada: **n8n 2.46.6**.

## 2.1 Archivos

```text
docker/n8n/
├── iniciar.sh                         # prepara, importa credenciales y flujos, los publica y arranca n8n
├── preparar.js                        # declara el exchange `eventos` y arma el JSON de credenciales desde el entorno
├── flujos/
│   ├── incidencia-registrada.json     # ID fijo `incidenciaRegistrada`
│   └── recordatorio-labores.json      # ID fijo `recordatorioLabores`
└── secretos/                          # fuera del repositorio (.gitignore), salvo .gitkeep
    └── firebase-cuenta-servicio.json  # lo descarga el usuario (T01)
```

## 2.2 Docker Compose y `.env.example`

Solo cambia el servicio `n8n` (perfiles `n8n` y `todo`):

| Cambio | Detalle |
|---|---|
| Imagen | `docker.n8n.io/n8nio/n8n:2.46.6` (antes `latest`) |
| Volumen | `./docker/n8n:/opt/agro:ro`, además del volumen de datos |
| Arranque | `entrypoint: ["sh", "/opt/agro/iniciar.sh"]` |
| Dependencias | `rabbitmq` sano |
| Memoria | `mem_limit: 896m` y `NODE_OPTIONS=--max-old-space-size=640`: con 512 MB, n8n 2.x se queda sin memoria al arrancar |
| Entorno | `x-keycloak-env` (para `KEYCLOAK_TOKEN_URL`), `N8N_ENCRYPTION_KEY`, `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`, `API_GATEWAY_URL`, `N8N_CLIENT_SECRET`, `RABBITMQ_HOST/PORT/USER/PASSWORD/VHOST/SSL` (como operaciones), `FIREBASE_PROYECTO_ID`, `FIREBASE_CUENTA_SERVICIO`, `GENERIC_TIMEZONE` y `TZ` |

`.env.example` suma `N8N_ENCRYPTION_KEY` (valor de desarrollo) y `FIREBASE_PROYECTO_ID` (vacío, T01). Cambiar `N8N_ENCRYPTION_KEY` con un volumen ya creado impide arrancar n8n: hay que borrar el volumen `n8n-data`.

## 2.3 Credenciales

`preparar.js` imprime un JSON con dos credenciales de ID fijo. `n8n import:credentials` lo cifra con `N8N_ENCRYPTION_KEY`:

| ID | Tipo de n8n | Campos |
|---|---|---|
| `rabbitmqAgro` | `rabbitmq` | `hostname`, `port`, `username`, `password`, `vhost`, `ssl` (TLS solo en la nube, `RABBITMQ_SSL=true`) |
| `firebaseFcm` | `googleApi` | `email` y `privateKey` (`client_email` y `private_key` del archivo de la cuenta de servicio), `httpNode: true`, `scopes: https://www.googleapis.com/auth/firebase.messaging` |

Keycloak no usa credencial de n8n (D-N8N-08).

## 2.4 Flujo `incidencia-registrada`

| # | Nodo | Qué hace |
|---|---|---|
| 1 | RabbitMQ Trigger (`evento`) | Declara la cola durable `n8n.incidencias` (`assertQueue`, `durable`) y la enlaza al exchange `eventos` con `operaciones.incidencia.registrada`; parsea el JSON (`jsonParseBody`, `onlyContent`); confirma el mensaje al recibirlo (`acknowledge: immediately`, D-N8N-09); credencial `rabbitmqAgro` |
| 2 | Code (`mensaje`) | Arma título y prioridad según `datos.tipo` (`PLAGA` → "Plaga registrada" y alta, `ENFERMEDAD` → "Enfermedad registrada" y alta, `DANIO` → "Daño registrado" y normal, `OTRO` → "Otra incidencia registrada" y normal), el cuerpo "<registradaPor.nombre>: <descripción hasta 100 caracteres>" y `data`. Un `datos.tipo` desconocido hace fallar la ejecución |
| 3 | HTTP Request (`fcm`) | El envío de 2.6 |

El trigger enlaza la cola pero no declara el exchange. Lo declara `preparar.js` (topic, durable, igual que los servicios), así el enlace funciona aunque operaciones no haya arrancado nunca.

## 2.5 Flujo `recordatorio-labores`

| # | Nodo | Qué hace |
|---|---|---|
| 1a | Schedule Trigger (`cada dia 07:00`) | Cron `0 7 * * *`, zona `America/La_Paz` (ajuste del flujo) |
| 1b | Manual Trigger (`a mano`) | Para ejecutarlo desde la interfaz o la CLI (la CLI lo exige) |
| 2 | Code (`conteo`) | Calcula `ayer`, `hoy` y `manana` en UTC; pide un token a Keycloak (*client credentials*, client `n8n`, secreto de `$env`); recorre las páginas de `GET {API_GATEWAY_URL}/api/operaciones/v1/labores?estado=PROGRAMADA&limite=100` con `fechaHasta={ayer}` y con `fechaDesde={hoy}&fechaHasta={manana}`, siguiendo `siguienteCursor` hasta `null`; arma la notificación. Si los dos conteos son 0 no devuelve nada y el flujo termina sin enviar |
| 3 | HTTP Request (`fcm`) | El envío de 2.6 |

## 2.6 Envío a FCM (común a los dos flujos)

`POST https://fcm.googleapis.com/v1/projects/{{ $env.FIREBASE_PROYECTO_ID }}/messages:send`, credencial `firebaseFcm`, cuerpo `{ "message": $json.mensaje }`, donde el nodo Code arma:

```json
{
  "topic": "tecnicos",
  "notification": { "title": "…", "body": "…" },
  "data": { "tipo": "…" },
  "android": { "priority": "high" }
}
```

Los valores de `data` van como texto, como exige FCM. FCM responde `{ "name": "projects/<id>/messages/<n>" }`, que queda en el historial (RQ-N8N-05).

## 2.7 `iniciar.sh`

1. `node /opt/agro/preparar.js > /tmp/credenciales.json`. Si falta una variable, el archivo de Firebase o RabbitMQ no responde, avisa en el log (`[agro] …`) y no importa nada: n8n arranca igual.
2. `n8n import:credentials` y borra el archivo.
3. `n8n import:workflow --separate --input=/opt/agro/flujos/`. Con IDs fijos, reimportar reemplaza en lugar de duplicar.
4. `n8n publish:workflow --id=<id>` para cada flujo (en 2.x los flujos se publican; `update:workflow` está obsoleto).
5. `exec n8n start`.

## 2.8 Verificación

Sin script (D-N8N-06). Con los perfiles `backend` y `n8n`:

1. **Incidencia (CE-N8N-01):** registrar una incidencia desde Vue o Flutter, o publicar un evento de prueba en el exchange `eventos` con routing key `operaciones.incidencia.registrada` desde el panel de RabbitMQ (`http://localhost:15672`). En `http://localhost:5678` → *Executions*, la ejecución de `incidencia-registrada` debe estar en verde y el nodo `fcm` debe mostrar el `name`.
2. **Recordatorio (CE-N8N-02):** con al menos una labor `PROGRAMADA` retrasada o para hoy o mañana, ejecutar el flujo desde la interfaz (*Execute workflow*) o por CLI:

   ```bash
   docker compose exec -e N8N_RUNNERS_BROKER_PORT=5690 -e N8N_PORT=5691 n8n n8n execute --id=recordatorioLabores
   ```

   Los dos puertos son para no chocar con el n8n que ya corre. La salida debe terminar con `"status": "success"`, `"lastNodeExecuted": "fcm"` y un `name` de FCM. Sin labores, termina en `conteo` y no envía nada.

Verificado el 2026-11-07: los dos flujos terminaron con éxito y FCM devolvió el ID del mensaje.

## 2.9 Documentación

- `README.md`: perfil `n8n`, Firebase (T01) y verificación (2.8).
- `servicio-operaciones/specs/spec-labores.md` 1.7: el supuesto "los recordatorios van al correo del responsable" se marca como reemplazado por esta spec.

## 2.10 Decisiones

| ID | Decisión | Motivo |
|---|---|---|
| D-N8N-01 | Tema `tecnicos` en lugar de tokens por dispositivo | Las labores programadas no tienen técnico asignado y las incidencias interesan a todos los técnicos; no hace falta guardar tokens ni cambiar servicios. |
| D-N8N-02 | Aviso inmediato de incidencias en la fase 1 | Lo dispara una acción del técnico y se puede demostrar en vivo en la defensa; usa un evento que ya existe. |
| D-N8N-03 | El recordatorio es un aviso diario con conteos | Evita un aviso por labor; el detalle está en la app. |
| D-N8N-04 | Credencial Google Service Account de n8n para FCM | n8n obtiene y renueva el token OAuth2 de Google; no hace falta firmar un JWT en un nodo Code. |
| D-N8N-05 | Flujos y credenciales importados al arrancar, con IDs fijos | Entorno reproducible sin pasos manuales, como el realm de Keycloak; reimportar no duplica. |
| D-N8N-06 | Verificación manual con el historial de n8n y la CLI, sin script | Lo más simple que demuestra el envío; la prueba real es el teléfono (CE-N8N-04). |
| D-N8N-07 | Correos en una fase 2 opcional | El push es la exigencia; los correos son el resto del Módulo 8, si queda tiempo. |
| D-N8N-08 | El recordatorio consulta operaciones en un solo nodo Code | Evita la credencial OAuth2 de Keycloak y la paginación por configuración del HTTP Request; el token se pide en cada ejecución. |
| D-N8N-09 | El trigger confirma el mensaje al recibirlo | Un evento con n8n apagado espera en la cola durable, y un fallo de FCM no provoca reentregas sin fin. |

---

# 3. Tareas

**Fase 1**

- [x] **T01** — (Usuario) Crear un proyecto de Firebase, generar una clave de su cuenta de servicio (Configuración del proyecto → Cuentas de servicio) y guardarla como `docker/n8n/secretos/firebase-cuenta-servicio.json`; poner el ID del proyecto en `FIREBASE_PROYECTO_ID` del `.env`. *Hecho cuando:* el archivo existe y no aparece en `git status`.
- [x] **T02** — Fijar la versión de n8n (2.46.6) y confirmar los campos de las credenciales, el comportamiento del RabbitMQ Trigger y los comandos de publicación y ejecución. *Hecho cuando:* los datos quedan anotados en 2.3, 2.4, 2.7 y 2.8.
- [x] **T03** — Escribir `preparar.js`, `iniciar.sh`, `.gitignore` de `secretos/` y los cambios de Docker Compose y `.env.example`. *Hecho cuando:* con el volumen vacío, `docker compose --profile n8n up -d` arranca, las credenciales aparecen en la interfaz y un reinicio no las duplica.
- [x] **T04** — Flujo `incidencia-registrada` con su ID fijo. *Hecho cuando:* tras recrear el volumen, el flujo aparece importado y activo, y la cola `n8n.incidencias` está enlazada al exchange `eventos`.
- [x] **T05** — Flujo `recordatorio-labores` con su ID fijo. *Hecho cuando:* tras recrear el volumen, el flujo aparece importado y activo.
- [x] **T06** — Verificar CE-N8N-01 y CE-N8N-02 con los perfiles `backend` y `n8n` (2.8).
- [x] **T07** — Actualizar `README.md` y `spec-labores.md` 1.7 (2.9). Comprobar CE-N8N-03.
- [ ] **T08** — Prueba en un teléfono (CE-N8N-04). *Bloqueada* hasta que exista la app Flutter.

**Fase 2 (opcional, si hay tiempo)**

- [ ] **T09** — Agregar Mailpit a Docker Compose (perfil `n8n`), una credencial SMTP y las variables de los destinatarios.
- [ ] **T10** — Correo de stock bajo (RF-29) desde el exchange `eventos`, con su propia cola, y correo de incidencias al administrador (RF-31) en el flujo `incidencia-registrada`. Cerrar la T07 de `servicio-inventario/specs/spec-stock-bajo.md`.
- [ ] **T11** — Flujo del reporte semanal (RF-34).
- [ ] **T12** — Verificación de los correos.
