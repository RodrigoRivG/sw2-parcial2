# SW2 Parcial 2 — Entorno de desarrollo con Docker

Entorno local compartido del sistema de gestión de campañas agrícolas (RNF-19): infraestructura, emuladores de nube e imágenes de desarrollo para los cuatro microservicios, el API Gateway y el servidor GraphQL. Está pensado para una laptop de **16 GB de RAM** con Windows 11 y WSL 2.

Cada carpeta `servicios/<servicio>/` empieza con su `Constitucion.md` y sus specs (`specs/`); el código se genera siguiendo spec → plan → tareas. Hoy tienen código `servicio-gestion`, `servicio-inventario`, `servicio-operaciones`, `servicio-ia`, `api-gateway` y `graphql-server`.

> Los microfrontends (single-spa con Angular, React y Vue) viven en su propio repositorio, `sw2-parcial2-app`, se desarrollan en Windows sin Docker y consumen el backend a través del API Gateway (`localhost:8080`) y Keycloak (`localhost:8180`), con la aplicación servida en `localhost:9000`. La app Flutter también queda fuera de este repositorio.

---

## Estructura

```
sw2-parcial2/
├── .github/workflows/         # un pipeline por servicio, filtrado por su carpeta (los seis de servicios/)
├── docker-compose.yml
├── .env.example
├── specs/                     # specs transversales: realm de Keycloak y n8n
├── scripts/
│   ├── ejecutar.sh             # corre comandos y tests en la imagen de un servicio
│   └── verificar-realm.py      # comprueba clients, roles y tokens del realm (spec-keycloak-realm.md)
├── docker/
│   ├── spring/                 # imagen de desarrollo: servicio-gestion y api-gateway
│   ├── node/                   # imagen de desarrollo: servicio-inventario y graphql-server
│   ├── laravel/                # imagen de desarrollo: servicio-operaciones
│   ├── fastapi/                # imagen de desarrollo: servicio-ia (también para entrenar el clasificador)
│   ├── postgres/init.sql       # crea gestion_db y keycloak_db
│   ├── localstack/init/        # crea el bucket S3 de evidencias
│   ├── keycloak/realms/        # realm exportado (se importa al arrancar Keycloak)
│   └── n8n/                    # flujos de notificaciones push, preparación e inicio (spec-n8n.md)
└── servicios/                  # cada uno con Constitucion.md, specs/, código y su Dockerfile de producción
    ├── servicio-gestion/           # Spring Boot
    ├── servicio-inventario/        # NestJS
    ├── servicio-operaciones/       # Laravel
    ├── servicio-ia/                # FastAPI (modelos de ML, visión, agentes y reportes)
    ├── api-gateway/                # Spring Cloud Gateway
    └── graphql-server/             # Apollo Server
```

`frontends/` (ignorada por Git) guarda solo los borradores de la constitución y las specs de los microfrontends, que después se copian a `sw2-parcial2-app`.

---

## 1. Primer arranque

En la terminal de **Ubuntu** (o la de VS Code conectada a WSL):

```bash
cd ~/proyectos/sw2-parcial2
cp .env.example .env
docker compose up -d
docker compose ps -a
```

Esto levanta la infraestructura base: PostgreSQL, MongoDB (replica set), DynamoDB Local y RabbitMQ. Todos deberían quedar `healthy` o `running`.

Panel de RabbitMQ: http://localhost:15672 (credenciales del `.env`).

### Token de LocalStack (para servicio-operaciones)

Desde marzo de 2026, LocalStack exige una cuenta. El plan **Hobby** es gratuito para uso no comercial:

1. Crea una cuenta en https://app.localstack.cloud.
2. Copia tu token de autenticación en `LOCALSTACK_AUTH_TOKEN` dentro del `.env`.

Solo hace falta para los perfiles que incluyen `servicio-operaciones`.

---

## 2. Perfiles: enciende solo lo que uses

| Perfil | Qué levanta (además de la base) | RAM extra aprox. |
|---|---|---|
| `gestion` | servicio-gestion | ~0,8 GB |
| `inventario` | servicio-inventario | ~0,3 GB |
| `operaciones` | servicio-operaciones + LocalStack (S3) | ~0,8 GB |
| `ia` | servicio-ia + MongoDB y S3 (LocalStack) | 0,8–3,5 GB |
| `gateway` | api-gateway | ~0,7 GB |
| `graphql` | graphql-server | ~0,2 GB |
| `auth` | Keycloak | ~0,7 GB |
| `n8n` | n8n (notificaciones push) | ~0,5 GB |
| `herramientas` | Interfaz web de DynamoDB | ~0,1 GB |
| `saga` | gestion + inventario + operaciones | ~1,9 GB |
| `backend` | los 3 de negocio + gateway + Keycloak | ~3,3 GB |
| `todo` | todo | ~8–9 GB |

```bash
docker compose --profile inventario up -d          # un servicio
docker compose --profile saga --profile auth up -d # varios perfiles
docker compose --profile todo down                  # apagar todo (datos conservados)
```

Un servicio solo arranca cuando su carpeta ya tiene el proyecto (por ejemplo, `pom.xml`, `package.json`, `composer.json` o `pyproject.toml`).

---

## 3. Contrato del entorno con cada servicio

Todo lo que un servicio necesita le llega por **variables de entorno** (RNF-03). Al implementar un servicio, su configuración debe leer estas variables:

### Comunes a todos

| Variable | Uso |
|---|---|
| `KEYCLOAK_JWKS_URI` | Claves para validar la firma del JWT (red interna) |
| `KEYCLOAK_ISSUER` | Emisor esperado (`iss`): `http://localhost:8180/realms/agro` |
| `KEYCLOAK_AUDIENCE` | Audiencia esperada (`aud`): el nombre del servicio |
| `KEYCLOAK_TOKEN_URL` | Para obtener tokens de cuenta de servicio (client credentials) |

### Por servicio

| Servicio | Arranque en desarrollo | Variables propias |
|---|---|---|
| servicio-gestion | `mvn spring-boot:run` (recompila al guardar; requiere `spring-boot-devtools`) | `SERVER_PORT`, `SPRING_DATASOURCE_*`, `SPRING_RABBITMQ_*` |
| servicio-inventario | `npm run start:dev` (recompila al guardar; aplica las migraciones de `migrations/` al arrancar) | `PORT`, `MONGODB_URI`, `RABBITMQ_URL` |
| servicio-operaciones | `php artisan serve` (crea las tablas de DynamoDB al arrancar); `servicio-operaciones-programador` corre `php artisan schedule:work` | `DYNAMODB_ENDPOINT`, `AWS_*`, `AWS_ENDPOINT`, `AWS_ENDPOINT_PUBLICO`, `AWS_BUCKET`, `RABBITMQ_*`, `API_GATEWAY_URL`, `KEYCLOAK_CLIENT_ID/SECRET` |
| servicio-ia | `pip install -e .` + `uvicorn app.main:app --reload` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `WHISPER_*`, `MONGODB_URI`, `MONGODB_BASE`, `AWS_BUCKET`, `AWS_ENDPOINT`, `S3_PREFIJO`, `RABBITMQ_URL`, `API_GATEWAY_URL`, `KEYCLOAK_CLIENT_ID/SECRET` |
| api-gateway | `mvn spring-boot:run` | `SERVER_PORT`, `GESTION_URL`, `INVENTARIO_URL`, `OPERACIONES_URL`, `IA_URL`, `GRAPHQL_URL`, `CORS_ORIGENES_PERMITIDOS`, `GATEWAY_TIEMPO_LIMITE` (10 s), `GATEWAY_TIEMPO_LIMITE_SINCRONIZACION` (120000 ms) |
| graphql-server | `npm run dev` (recarga al guardar) | `PORT`, `API_GATEWAY_URL`, `KEYCLOAK_AUDIENCE`, `KEYCLOAK_CLIENT_ID/SECRET`, `GRAPHQL_TIEMPO_LIMITE_LLAMADA_MS` (4000), `GRAPHQL_PLAZO_CONSULTA_MS` (4500), `GRAPHQL_MAXIMO_LLAMADAS` (200) |

Los servicios se comunican entre sí **solo a través del API Gateway** (`API_GATEWAY_URL`), como exigen las constituciones. Solo el gateway conoce las URL internas.

IA usa MongoDB (base `ia_db`) y S3 (prefijo `ia/`). En local, `AWS_ENDPOINT` apunta a LocalStack; en la nube se omite. El mismo clúster y bucket sirven a otros servicios con bases y prefijos separados.

---

## 4. Ejecutar comandos y tests sin instalar nada

`scripts/ejecutar.sh` corre cualquier comando dentro de la imagen de desarrollo de un servicio, con acceso a Docker para **Testcontainers** y a la red de Compose:

```bash
./scripts/ejecutar.sh servicio-gestion mvn -B verify
./scripts/ejecutar.sh api-gateway mvn -B verify
./scripts/ejecutar.sh servicio-inventario npm test -- --coverage
./scripts/ejecutar.sh servicio-inventario npm run lint
./scripts/ejecutar.sh servicio-operaciones ./vendor/bin/pest
./scripts/ejecutar.sh servicio-ia pytest
./scripts/ejecutar.sh servicio-ia mypy app
./scripts/ejecutar.sh graphql-server npm test -- --coverage
```

También sirve para los generadores y herramientas de cada stack (`composer`, `php artisan`, `npx @nestjs/cli`, `mvn`, `pip`…).

Versiones de las imágenes: Java 21 + Maven 3.9, Node 24 LTS, PHP 8.4 + Composer 2, Python 3.12.

---

## 5. Puertos y URLs

| Servicio | Desde tu máquina | Desde otro contenedor |
|---|---|---|
| api-gateway | http://localhost:8080 | `http://api-gateway:8080` |
| servicio-gestion | http://localhost:8081 | `http://servicio-gestion:8081` |
| servicio-inventario | http://localhost:3000 | `http://servicio-inventario:3000` |
| servicio-operaciones | http://localhost:8000 | `http://servicio-operaciones:8000` |
| servicio-ia | http://localhost:8001 | `http://servicio-ia:8000` |
| graphql-server | http://localhost:4000 | `http://graphql-server:4000` |
| Keycloak | http://localhost:8180 | `http://keycloak:8080` |
| n8n | http://localhost:5678 | `http://n8n:5678` |
| RabbitMQ | `localhost:5672`, panel en http://localhost:15672 | `rabbitmq:5672` |
| PostgreSQL | `localhost:5432` | `postgres:5432` |
| MongoDB | `mongodb://localhost:27017/?directConnection=true` | `mongodb://mongo:27017/?replicaSet=rs0` |
| DynamoDB Local | http://localhost:8002 | `http://dynamodb:8000` |
| LocalStack (S3) | http://localhost:4566 | `http://localstack:4566` |
| Admin de DynamoDB | http://localhost:8003 | — |

Dentro de un contenedor, `localhost` es el propio contenedor: usa siempre la columna derecha.

Para MongoDB Compass desde Windows usa `directConnection=true`. Sin eso, Compass intentaría conectarse al nombre interno `mongo`, que tu máquina no conoce.

---

## 6. Diferencias entre local y la nube

La construcción y las comprobaciones previas al despliegue están documentadas en
[`docs/verificacion-imagenes-produccion.md`](docs/verificacion-imagenes-produccion.md).
La configuración para las tres copias del backend y los servicios compartidos
está en [`despliegue/README.md`](despliegue/README.md).

| Componente | Local (Docker) | Nube |
|---|---|---|
| PostgreSQL | `postgres:17` | Azure Database for PostgreSQL |
| MongoDB | `mongo:8.0`, replica set sin autenticación | MongoDB Atlas (con autenticación) |
| DynamoDB | DynamoDB Local | Amazon DynamoDB |
| S3 | LocalStack (los objetos no persisten entre reinicios: las fotos de incidencias anteriores responden `404 NoSuchKey`) | Amazon S3 |
| RabbitMQ | AMQP sin TLS | CloudAMQP con AMQPS |
| Ollama | Nativo en Windows (usa tu GPU) | Permanece en la máquina del usuario; exposición segura pendiente para la última etapa |

El código es el mismo: solo cambian las variables de entorno.

---

## 7. Notas

### Keycloak y los tokens

Keycloak está configurado para que el emisor (`iss`) sea siempre `http://localhost:8180/realms/agro`, se pida el token desde el navegador o desde un contenedor. Por eso los servicios validan la firma con `KEYCLOAK_JWKS_URI` (red interna) y comparan el emisor con `KEYCLOAK_ISSUER`.

En Spring Boot, eso significa configurar `jwk-set-uri` junto con `issuer-uri`: las claves se descargan de `jwk-set-uri` y el emisor solo se compara. Con `issuer-uri` solo, intentaría conectarse a `localhost:8180` desde dentro del contenedor.

El realm `agro` está en `docker/keycloak/realms/realm-agro.json` y Keycloak lo importa al arrancar (`specs/spec-keycloak-realm.md`). Trae los roles, un Audience mapper por servicio, las cuentas de servicio (`servicio-operaciones`, `servicio-ia`, `graphql-server`, `n8n`) y estos usuarios de prueba, con la contraseña `KEYCLOAK_CLAVE_USUARIOS_PRUEBA` del `.env`:

| Usuario | Roles |
|---|---|
| `admin.prueba` | `administrador` (y gestión de usuarios, RF-32) |
| `tecnico.prueba` | `tecnico_campo` |
| `gerencia.prueba` | `gerencia` |
| `multirol.prueba` | `administrador`, `gerencia` |

El JSON no tiene secretos: usa `${VARIABLE}` y Keycloak los toma del `.env` al importar. Para un token de prueba con `curl`, usa el client `agro-pruebas` (solo desarrollo):

```bash
curl -s -d grant_type=password -d client_id=agro-pruebas -d username=tecnico.prueba -d password=prueba123 \
  http://localhost:8180/realms/agro/protocol/openid-connect/token
```

Para verificar el realm (y, con `--saga`, la Saga de punta a punta con `--profile saga --profile gateway --profile auth`):

```bash
python3 scripts/verificar-realm.py --saga
```

La importación se omite si el realm ya existe. Para aplicar cambios del JSON, borra el realm y reinicia Keycloak:

```bash
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh delete realms/agro \
  --server http://localhost:8080 --realm master --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD"
docker compose restart keycloak
```

### n8n y las notificaciones push

n8n envía dos avisos push por Firebase Cloud Messaging al tema `tecnicos`: uno inmediato por cada incidencia registrada y un recordatorio diario (07:00) de labores programadas (`specs/spec-n8n.md`). Al arrancar, importa y publica los flujos y sus credenciales desde `docker/n8n/`, sin pasos manuales.

Antes del primer arranque (una sola vez):

1. En la consola de Firebase, crea un proyecto y genera una clave de su cuenta de servicio (Configuración del proyecto → Cuentas de servicio).
2. Guárdala como `docker/n8n/secretos/firebase-cuenta-servicio.json` (está en `.gitignore`).
3. En el `.env`, pon el `project_id` del archivo en `FIREBASE_PROYECTO_ID` y define `N8N_ENCRYPTION_KEY` (copia la de `.env.example`).

Sin esto n8n arranca igual, pero sin flujos (lo avisa en el log con `[agro]`). Si cambias `N8N_ENCRYPTION_KEY` después del primer arranque, borra el volumen: `docker volume rm sw2_n8n-data`.

Para verificar (con `--profile backend --profile n8n`):

- **Incidencia:** registra una incidencia, o publica un evento con routing key `operaciones.incidencia.registrada` en el exchange `eventos` desde el panel de RabbitMQ. En http://localhost:5678 → *Executions*, la ejecución debe estar en verde y el nodo `fcm` debe mostrar el `name` del mensaje.
- **Recordatorio (también para la defensa):** abre el flujo `recordatorio-labores` y pulsa *Execute workflow*, o ejecútalo por CLI:

  ```bash
  docker compose exec -e N8N_RUNNERS_BROKER_PORT=5690 -e N8N_PORT=5691 n8n n8n execute --id=recordatorioLabores
  ```

  Solo envía algo si hay labores `PROGRAMADA` retrasadas o para hoy o mañana.

### Ollama (nativo en Windows)

1. Instálalo desde https://ollama.com.
2. En PowerShell: `ollama pull qwen2.5:3b`.
3. Desde el contenedor de `servicio-ia` se alcanza en `http://host.docker.internal:11434`.

Si el contenedor no logra conectarse, crea la variable de entorno de Windows `OLLAMA_HOST=0.0.0.0`, reinicia Ollama y permite el acceso en el firewall.

### Recarga en caliente

- **Spring Boot:** el contenedor recompila al guardar en `src/main` y DevTools reinicia la app.
- **NestJS, Apollo y FastAPI:** recargan solos.
- **Laravel:** PHP lee el código en cada petición.

Tras cambiar dependencias, reinicia el servicio: `docker compose restart <servicio>`.

---

## Comandos del día a día

```bash
docker compose ps                            # qué está corriendo
docker compose logs -f servicio-inventario     # logs en vivo
docker compose restart servicio-operaciones     # reiniciar un servicio
docker compose exec servicio-operaciones php artisan route:list
docker stats                                 # RAM y CPU por contenedor
docker compose --profile todo down -v         # apagar y BORRAR todos los datos
```

## Problemas comunes

- **"Permission denied" al editar archivos:** `sudo chown -R $USER:$USER ~/proyectos/sw2-parcial2`.
- **Un contenedor se reinicia solo:** probablemente se quedó sin memoria. Revisa `docker stats` y apaga perfiles.
- **`servicio-inventario` muestra `JavaScript heap out of memory` al arrancar:** la verificación de tipos de `nest start --watch` necesita unos 300 MB. El script `start:dev` ya sube el heap de Node a 384 MB; si se cambió, restáuralo.
- **"port is already allocated":** otro programa usa ese puerto. Cambia la parte izquierda de `ports:` (por ejemplo `"8091:8081"`).
- **Una base de `init.sql` no existe:** ese archivo solo se ejecuta al crear el volumen de Postgres. Recréalo con `docker compose down -v` (borra los datos).
- **LocalStack no arranca:** revisa que `LOCALSTACK_AUTH_TOKEN` esté en el `.env` con `docker compose logs localstack`.
- **Descargas que se cortan (`EOF`):** vuelve a ejecutar el comando; lo descargado se conserva.
- **IA responde `503 MODELO_NO_DISPONIBLE` o `GET /api/ia/v1/modelos` devuelve `[]`:** no hay versiones publicadas en `ia_db` o faltan sus archivos en S3. El cambio de almacenamiento no migra los modelos anteriores. Hay que entrenarlos y publicarlos según `servicios/servicio-ia/docs/modelos.md` ("Cómo reentrenar y publicar"):
  - `rendimiento` y `patrones`: `docker compose exec servicio-ia python -m app.ml.entrenar <modelo> --incluir-historicos`, con el backend levantado. Tarda segundos.
  - `clasificador`: fuera del contenedor, con el resto del backend detenido salvo `mongo`, `localstack` y `rabbitmq`, porque necesita unos 3 GB. Tarda unos 15 minutos.
  - Después se publican desde `/admin/modelos` o con `POST /api/ia/v1/modelos/{nombre}/versiones/{n}/publicacion`.
- **La primera consulta tras levantar el backend es lenta:** los servicios tardan en responder su primer uso (por ejemplo, GraphQL puede agotar su plazo de 4,5 s y devolver datos parciales). Antes de una demostración, hacer una consulta de calentamiento.
