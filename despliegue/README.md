# Base de despliegue

Primero se desplegará **Azure Container Apps**, desde GitHub y con el mismo código
que se utiliza localmente. No se crean imágenes locales, VM ni recursos cloud al
preparar esta base. El Compose de la raíz sigue siendo de desarrollo.

La guía de ejecución y credenciales está en [azure/README.md](azure/README.md).

## Separación de cada despliegue

Cada nube tiene su frontend, Gateway, GraphQL, microservicios y configuración
propios. Las llamadas entre aplicaciones apuntan a su propio despliegue, nunca
al Gateway de otra nube. Keycloak también se configura para ese destino, con su
propia URL y base de autenticación; compartir el servidor PostgreSQL no exige
compartir la misma base de Keycloak.

Los recursos externos siguen siendo compartidos donde corresponda: PostgreSQL,
MongoDB, DynamoDB, S3, RabbitMQ y los servicios Google que actualmente usa IA.
No se reemplazó ningún adaptador ni base de datos. Firestore/GCS siguen siendo
necesarios para el código actual hasta que se decida e implemente un reemplazo.

Ollama/Qwen permanecen en la máquina del usuario. Whisper se ejecuta con el
servicio IA en la nube. El entrenamiento de rendimiento, patrones y clasificación
se debe ejecutar en la nube; este workflow de despliegue no lo ejecuta ni afirma
que ya esté realizado.

## Azure primero

La base Azure incluye diez aplicaciones a partir de ocho imágenes:

- Los cuatro microservicios, API Gateway y GraphQL.
- Keycloak y n8n, con bases PostgreSQL separadas.
- Programador y consumidor de operaciones, que reutilizan la imagen de operaciones.

Los consumidores de gestión, inventario e IA están activos en Azure. Sus procesos
y n8n se mantienen en una réplica para no depender de peticiones HTTP. El
programador, el consumidor de operaciones y n8n usan el Gateway de Azure.
La cuenta FCM se monta desde Key Vault; el estado de n8n va a PostgreSQL.

AWS y GCP conservan generadores de borrador para una etapa posterior, no un
pipeline activo ni una dependencia requerida por el backend de Azure. App Runner
sigue pendiente de confirmar acceso de la cuenta.

Antes de activar varias copias simultáneas, definir vhosts/colas y la coordinación
de tareas sobre los datos compartidos. No basta con activar tres schedulers sobre
las mismas tablas. Esto se resolverá al preparar el siguiente destino, sin hacer
que sus procesos llamen al backend de Azure.

## Preparación local sin construir imágenes

```bash
python3 scripts/preparar-despliegue.py --nube azure
python3 scripts/generar-serverless.py azure --borrador
python3 -m unittest discover -s despliegue -p 'test_*.py' -v
```

Las conexiones comunes se completan en `.env.despliegue.compartidos`; las URL,
identidades y diferencias de Azure, en `.env.despliegue.azure`. Este último tiene
prioridad. Los secretos existentes se conservan y `.env` no se modifica.
`KEYCLOAK_ISSUER` y los clientes deben corresponder al Keycloak de Azure.
Usar `CONSUMIDORES_ACTIVOS=true` y `N8N_NUBE=azure` para esta primera copia.

`generado/borrador/azure` no es una configuración lista para desplegar.
Sin `--borrador`, el generador exige el preflight de Azure y sus componentes
compartidos antes de producir `generado/listo/azure`. No se mostraron ni subieron
credenciales. Los catálogos `secretos.json` contienen valores privados, tienen
permisos 600, no se versionan ni se publican como artefactos.

Las pruebas son locales y con valores ficticios; no prueban conectividad,
permisos, cuotas ni arranque en Azure. Continúan pendientes las alertas de
inventario anotadas en `docs/verificacion-imagenes-produccion.md`.
