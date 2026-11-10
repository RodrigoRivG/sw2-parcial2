# Verificación de imágenes de producción

Fecha: 2026-11-09. Plataforma verificada: Linux/amd64, Docker Desktop.

Esta comprobación valida el empaquetado y el arranque previo al despliegue.
No constituye una prueba de integración con AWS, Azure o GCP.

## Resultados

| Imagen local | Construcción | Comprobación adicional |
|---|---|---|
| `sw2/servicio-gestion:verificacion` | Correcta | JAR ejecutable con Java 21; migraciones en PostgreSQL vacío y `/salud/readiness` con RabbitMQ temporal: HTTP 200, `UP` |
| `sw2/servicio-inventario:verificacion` | Correcta | Migraciones en MongoDB vacío y `/salud/readiness` con RabbitMQ temporal: HTTP 200, MongoDB y RabbitMQ `UP` |
| `sw2/servicio-operaciones:verificacion` | Correcta | Autoload y extensiones PHP; arranque de Apache en 8080 y `/salud/liveness`: HTTP 200, `UP` |
| `sw2/servicio-ia:verificacion` | Correcta | Importación de la aplicación y recursos; OpenCV, operación TensorFlow, generación PDF y carga de Whisper `small` sin internet |
| `sw2/api-gateway:verificacion` | Correcta | Arranque del JAR y `/salud/liveness`: HTTP 200, `UP` |
| `sw2/graphql-server:verificacion` | Correcta | Ejecutable y esquema incluidos; arranque y `/salud/liveness`: HTTP 200, `UP` |

Las imágenes se construyeron con los Dockerfiles de `servicios/`, sin leer `.env`
ni incorporar credenciales reales. Los contenedores de prueba utilizaron valores
ficticios. Las comprobaciones de salud de operaciones, Gateway y GraphQL se
ejecutaron sin red externa; no validan sus dependencias reales.

Las seis imágenes ejecutan sus procesos con usuarios sin privilegios de root.
No fue necesario modificar los Dockerfiles para completar las construcciones.
La imagen de IA ocupa aproximadamente 4,49 GB sin comprimir; incluye las
librerías de aprendizaje automático y el modelo Whisper. Su comprobación no
arrancó la API contra Firestore/GCS, RabbitMQ ni Ollama reales.

Gestión e inventario usaron una red Docker interna y contenedores nuevos de
PostgreSQL, MongoDB y RabbitMQ. Se retiraron los contenedores, sus volúmenes
anónimos y la red al terminar. No se usaron las bases ni las colas locales.
MongoDB temporal fue standalone: no se verificaron transacciones de negocio.

## Repetir la construcción

Desde la raíz del repositorio:

```bash
for servicio in servicio-gestion servicio-inventario servicio-operaciones servicio-ia api-gateway graphql-server; do
  docker build --progress=plain -t "sw2/${servicio}:verificacion" "servicios/${servicio}" || break
done
```

IA incluye Whisper `small` en la imagen y necesita descargar el modelo durante
la construcción. No se publicaron imágenes en ningún registro ni se desplegaron
servicios en la nube.

## Hallazgos pendientes

`npm audit --omit=dev` sobre el lockfile de inventario reportó cuatro entradas:

| Paquete | Severidad |
|---|---|
| `@nestjs/platform-express` | Alta, por dependencia afectada |
| `multer` | Alta |
| `@nestjs/swagger` | Moderada, por dependencia afectada |
| `js-yaml` | Moderada |

El informe de npm indica correcciones disponibles. Las entradas incluyen
dependencias directas y transitivas; no representan necesariamente cuatro fallos
independientes. No se actualizaron paquetes dentro de esta verificación de
empaquetado. Corresponde revisar las actualizaciones y ejecutar las pruebas de
inventario antes de exponer el despliegue públicamente.

## Siguiente etapa

- La configuración nativa para Cloud Run, App Runner (si la cuenta ya tiene
  acceso) y Container Apps está en `despliegue/`, con generador y validadores.
  El Compose de la raíz sigue siendo local; no se usan VM ni Caddy en nube.
- Configurar dominios, HTTPS, realm de Keycloak, credenciales y acceso de red
  a los recursos compartidos.
- Decidir dónde ejecutar los procesos programados sobre datos compartidos;
  no activar tres copias sin revisar sus bloqueos y efectos.
- Primer destino actual: Azure, con su propio Keycloak, n8n y procesos que usan
  únicamente el Gateway de Azure. Ver `despliegue/azure/README.md`.
- Publicar las imágenes y verificar primero un despliegue completo contra los
  recursos reales, incluidos IA/Ollama y push al teléfono.

La adaptación a servicios administrados agrega un arranque de credenciales a IA
y una bandera del consumidor en inventario. Se reconstruyeron con etiqueta local
`serverless` y se construyeron también `sw2/n8n:serverless` y
`sw2/keycloak:serverless` para incluir sus archivos sin montajes del repositorio.
Pasaron cuatro pruebas de consumidores y cuatro de contratos nativos, así como
compilación/lint de inventario y comprobaciones de ADC de IA. La tabla inicial
corresponde a la verificación previa; publicar las imágenes actualizadas al
desplegar. Ver el detalle y límites de la adaptación en `despliegue/README.md`.

No se ejecutó la suite completa de pruebas funcionales durante esta revisión.

Las imágenes locales de verificación y serverless se retiraron para recuperar
espacio. La base actual construirá las imágenes en ACR desde GitHub únicamente
al ejecutar manualmente el despliegue, cuando existan las credenciales. El modo
predeterminado del workflow solo valida configuración, sin Docker ni Azure.
