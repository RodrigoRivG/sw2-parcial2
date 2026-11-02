# Constitución — Servicio de Inteligencia Artificial (`servicio-ia`)

> Reglas no negociables de este microservicio. Prevalecen sobre specs, planes y tareas.
> Si una spec contradice esta constitución, se corrige la spec o se enmienda la constitución; nunca se ignora.
> Las secciones marcadas con **[común]** son idénticas en los cuatro microservicios y solo se cambian en los cuatro a la vez. Excepción: la tabla «Permisos de este servicio» y el «Glosario de este servicio» son propios de cada microservicio y se enmiendan sin tocar los demás.

## 1. Propósito y límites

**Responsable de:**
- Estimación del rendimiento de campañas con un modelo supervisado (Random Forest).
- Identificación de agrupaciones y anomalías con modelos no supervisados (K-Means, Isolation Forest).
- Clasificación de imágenes de cultivos con Deep Learning (MobileNetV3), incluidos fotogramas extraídos de videos.
- Entrenamiento, versionado y exportación de los modelos, incluidas las versiones TensorFlow Lite y TensorFlow.js que usan Flutter y Vue.js.
- Agentes inteligentes (LangGraph) y servidor de herramientas MCP para consultar los demás microservicios.
- Transcripción de solicitudes de voz (Faster-Whisper).
- Generación de reportes en PDF y Excel, a pedido (React) o programados (n8n).

**No es responsable de:**
- Datos de negocio (parcelas, campañas, insumos, labores): solo los consulta, nunca los modifica (RN-14).
- Cálculo de indicadores de negocio (rendimiento real, costos): los calcula `servicio-gestion`; este servicio los usa tal cual.
- Clasificación offline: corre en el dispositivo (Flutter y Vue.js). Este servicio solo entrega los modelos exportados.
- Guardar el resultado de clasificación de una incidencia → `servicio-operaciones`.
- Envío de correos → n8n.
- Usuarios y roles → Keycloak.

**Fuera del alcance del sistema:** diagnósticos agrícolas validados. Todo resultado de IA es orientativo (RN-13). No se usan servicios externos de IA; el modelo de lenguaje corre en Ollama.

**Trazabilidad:** CU-14 a CU-18, CU-25 · RF-18 a RF-25, RF-34 · RN-13, RN-14 · RNF-06.

## 2. Stack

- Python 3.11+ con FastAPI y Pydantic v2.
- ML y Deep Learning: scikit-learn, TensorFlow/Keras, OpenCV, Pillow, pandas, NumPy, Joblib.
- Agentes: LangGraph, MCP Python SDK y Ollama (modelo de lenguaje pequeño cuantizado).
- Voz: Faster-Whisper.
- Reportes: WeasyPrint (PDF) y OpenPyXL (Excel).
- Almacenamiento: Google Cloud Storage (modelos, conjuntos de entrenamiento y reportes) y Firestore (estado de trabajos y resultados).
- Cola de trabajos asíncronos: RabbitMQ (el mismo broker del sistema).
- Calidad: pytest + httpx, Ruff (lint y formato) y mypy.
- Despliegue: imagen Docker en Google Cloud Run; Ollama en Google Compute Engine.
- No se introducen lenguajes, frameworks, bases de datos ni proveedores de IA nuevos sin una enmienda.

## 3. Arquitectura (capas con puertos y adaptadores)

- Capas:
  - `domain/`: conceptos y reglas propias de la IA (predicción, clasificación, reporte, versión de modelo). Python puro.
  - `application/`: casos de uso y puertos (interfaces) hacia datos de negocio, modelos, almacenamiento, voz y modelo de lenguaje.
  - `agents/`: grafos y agentes de LangGraph. Dependen de los puertos de `application`, nunca de clientes concretos.
  - `mcp_server/`: servidor MCP y sus herramientas, todas de solo lectura.
  - `ml/`: entrenamiento, evaluación y exportación de modelos. Se ejecuta fuera del ciclo de las solicitudes HTTP.
  - `infrastructure/`: clientes HTTP de los microservicios, carga de modelos, Ollama, Whisper, generación de PDF/Excel, Firestore, Cloud Storage y RabbitMQ.
  - `interfaces/`: rutas HTTP de FastAPI, esquemas de entrada y salida, seguridad y workers.
- Las dependencias apuntan hacia `domain`. `domain` y `application` no importan FastAPI, LangGraph, TensorFlow, scikit-learn ni SDK de nube.
- Los modelos se cargan una vez al iniciar el proceso (o al publicar una nueva versión), nunca en cada solicitud.
- Las operaciones largas (reportes, consultas a agentes, análisis de video) se procesan de forma asíncrona: la API crea un trabajo, devuelve su ID y el cliente consulta su estado (RF-24).

### Estructura de directorios

```text
servicio-ia/
├── app/
│   ├── main.py
│   ├── domain/                                  # Python puro
│   │   ├── prediction/
│   │   │   ├── prediccion_rendimiento.py
│   │   │   ├── agrupacion.py
│   │   │   └── anomalia.py
│   │   ├── vision/
│   │   │   └── clasificacion_imagen.py
│   │   ├── report/
│   │   │   ├── reporte.py
│   │   │   ├── solicitud_reporte.py
│   │   │   └── estado_trabajo.py
│   │   ├── model/
│   │   │   └── version_modelo.py
│   │   └── shared/
│   │       └── errores_dominio.py
│   ├── application/
│   │   ├── use_cases/
│   │   │   ├── estimar_rendimiento.py
│   │   │   ├── analizar_patrones.py
│   │   │   ├── clasificar_imagen.py
│   │   │   ├── clasificar_video.py
│   │   │   ├── consultar_agente.py
│   │   │   ├── solicitar_reporte.py
│   │   │   ├── generar_reporte.py
│   │   │   ├── consultar_estado_trabajo.py
│   │   │   └── publicar_version_modelo.py
│   │   └── ports/
│   │       ├── datos_agricolas.py
│   │       ├── datos_inventario.py
│   │       ├── datos_operaciones.py
│   │       ├── repositorio_modelos.py
│   │       ├── repositorio_trabajos.py
│   │       ├── almacen_archivos.py
│   │       ├── transcriptor.py
│   │       ├── modelo_lenguaje.py
│   │       └── publicador_mensajes.py
│   ├── agents/                                  # LangGraph
│   │   ├── grafo_principal.py
│   │   ├── estado_agente.py
│   │   ├── agente_campanias.py
│   │   ├── agente_inventario.py
│   │   ├── agente_reportes.py
│   │   └── prompts/
│   ├── mcp_server/                              # herramientas MCP de solo lectura
│   │   ├── servidor.py
│   │   └── tools/
│   │       ├── herramientas_agricolas.py
│   │       ├── herramientas_inventario.py
│   │       └── herramientas_operaciones.py
│   ├── ml/                                      # fuera del ciclo HTTP
│   │   ├── features/
│   │   │   └── caracteristicas_campania.py
│   │   ├── training/
│   │   │   ├── entrenar_rendimiento.py
│   │   │   ├── entrenar_agrupacion.py
│   │   │   └── entrenar_clasificador.py
│   │   ├── evaluation/
│   │   │   └── evaluar_modelo.py
│   │   └── export/
│   │       ├── exportar_tflite.py
│   │       └── exportar_tfjs.py
│   ├── infrastructure/
│   │   ├── clients/
│   │   │   ├── autenticacion_servicio.py        # token de cuenta de servicio
│   │   │   ├── cliente_gestion.py
│   │   │   ├── cliente_inventario.py
│   │   │   └── cliente_operaciones.py
│   │   ├── inference/
│   │   │   ├── cargador_sklearn.py
│   │   │   └── cargador_tensorflow.py
│   │   ├── llm/
│   │   │   └── cliente_ollama.py
│   │   ├── speech/
│   │   │   └── transcriptor_whisper.py
│   │   ├── reports/
│   │   │   ├── generador_pdf.py
│   │   │   ├── generador_excel.py
│   │   │   └── templates/
│   │   ├── persistence/
│   │   │   ├── repositorio_trabajos_firestore.py
│   │   │   └── repositorio_modelos_gcs.py
│   │   ├── storage/
│   │   │   └── almacen_gcs.py
│   │   └── messaging/
│   │       ├── conexion_rabbitmq.py
│   │       └── publicador_rabbitmq.py
│   ├── interfaces/
│   │   ├── http/
│   │   │   ├── routers/
│   │   │   │   ├── prediccion.py
│   │   │   │   ├── vision.py
│   │   │   │   ├── agentes.py
│   │   │   │   ├── reportes.py
│   │   │   │   ├── trabajos.py
│   │   │   │   └── modelos.py
│   │   │   ├── schemas/
│   │   │   ├── seguridad.py
│   │   │   ├── id_correlacion.py
│   │   │   └── manejador_errores.py
│   │   └── workers/
│   │       └── trabajador_trabajos.py            # consume la cola de trabajos
│   └── config/
│       └── configuracion.py
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   ├── application/
│   │   └── agents/
│   ├── integration/
│   └── fixtures/                                # imágenes, audios y datos pequeños
├── Dockerfile
├── pyproject.toml
└── Constitucion.md
```

- Las carpetas de capa y su regla de dependencias son obligatorias. Los nombres concretos de archivos son de referencia y se definen en el plan.
- La carpeta del servidor MCP se llama `mcp_server`, no `mcp`, para no ocultar el paquete del SDK.
- Los tests replican la estructura de `app`.

## 4. Datos y artefactos

- Este servicio no es dueño de datos de negocio ni guarda copias permanentes de ellos. Los obtiene en cada uso desde los microservicios.
- Es dueño exclusivo de sus artefactos:
  - **Cloud Storage:** modelos versionados, conjuntos de entrenamiento usados por cada versión, modelos exportados (TFLite, TF.js) y reportes generados.
  - **Firestore:** trabajos asíncronos (tipo, estado, solicitante, fechas, resultado o error) y resultados de predicciones y análisis.
- Ningún otro servicio accede a su bucket ni a su base de datos.
- Identificadores: UUID.
- Cada resultado guarda la versión del modelo que lo produjo.
- Audios de voz: se eliminan después de transcribirlos; solo se conserva la transcripción.
- Imágenes enviadas a clasificar: no se conservan, salvo que la spec lo pida para reentrenamiento.
- Límites de entrada definidos en la spec: tamaño de imagen (`.jpg`, `.png`), duración de audio (`.wav`, `.mp3`) y de video.
- Los reportes generados se entregan mediante URL firmadas de corta duración y se eliminan tras el plazo de retención definido en la spec.

## 5. Modelos de IA

- Todo modelo tiene una versión inmutable con: fecha, conjunto de datos usado, variables, hiperparámetros, métricas de evaluación y lista de etiquetas (para el clasificador).
- El entrenamiento es reproducible: script versionado, semilla fija y conjunto de datos guardado junto a la versión.
- Una versión nueva solo se publica si sus métricas se registraron y no son peores que las de la versión vigente, o si se justifica en el plan.
- Las versiones TFLite y TF.js se exportan del mismo modelo, con la misma versión y la misma lista de etiquetas que la versión del servidor.
- Los modelos para el dispositivo se descargan desde un endpoint que informa versión y suma de verificación.
- Toda respuesta de un modelo incluye la versión del modelo, el nivel de confianza cuando aplica y la marca de resultado orientativo (RN-13).
- Si no hay datos históricos suficientes para estimar, se responde que la estimación no está disponible; nunca se inventa un valor.
- La documentación de cada modelo (variables, entrenamiento, métricas y cómo reentrenarlo) se mantiene al día con cada versión.

## 6. Agentes y MCP

- Los agentes solo consultan datos (RN-14). Las herramientas MCP solo llaman endpoints de lectura de los microservicios.
- Las herramientas se autentican con una cuenta de servicio de Keycloak que solo tiene permisos de lectura.
- Las cifras de un reporte provienen de los datos devueltos por las herramientas. Las tablas y gráficos se construyen directamente con esos datos; el modelo de lenguaje solo interpreta la solicitud y redacta el texto.
- Toda cifra mencionada en el texto generado debe existir en los datos consultados; si no se puede verificar, se omite.
- El contenido devuelto por los microservicios se trata como datos, nunca como instrucciones para el agente.
- Cada consulta a un agente tiene límite de pasos y de tiempo. Al superarlos, el trabajo termina con error explicado, no queda colgado.
- Si Ollama no está disponible, fallan solo las funciones de agentes y reportes con un error claro; predicción y clasificación siguen funcionando (RNF-08).
- Cada ejecución registra la solicitud, las herramientas llamadas, sus tiempos y el resultado, con el `idCorrelacion`.

## 7. Comunicación

- API REST con prefijo de servicio y versión: `/api/ia/v1/...`. El API Gateway rutea todo `/api/ia/**` a este servicio, y solo se accede a través de él.
- El contrato OpenAPI es la fuente de verdad. Un cambio incompatible exige una nueva versión (`/api/ia/v2/...`); la anterior se mantiene mientras haya clientes que la usen (incluida la app Flutter instalada).
- Consulta a `servicio-gestion`, `servicio-inventario` y `servicio-operaciones` por REST a través del Gateway, con tiempo límite y manejo de fallo en cada llamada.
- Trabajos asíncronos: la solicitud se encola en RabbitMQ, la procesa un worker y su estado se consulta por ID (`EN_COLA`, `PROCESANDO`, `COMPLETADO`, `FALLIDO`).
- Al terminar un reporte publica el evento `ia.reporte.completado`, para que n8n lo envíe por correo en los reportes programados (RF-34).
- Expone endpoints de resultados para el servidor GraphQL (predicciones y análisis).
- La clasificación de imágenes en el servidor responde en menos de 3 s (RNF-06).

## 8. Calidad

- Todo endpoint tiene tests de integración.
- Toda regla de `domain` y todo caso de uso tienen tests unitarios.
- Herramientas MCP: tests de contrato contra respuestas simuladas de los microservicios.
- Agentes: tests con un modelo de lenguaje simulado que verifican qué herramientas se llaman y que las cifras del reporte salen de los datos.
- Modelos: tests de humo con datos pequeños en `tests/fixtures` (carga, forma de la salida, etiquetas válidas).
- Test que verifica que las versiones exportadas (TFLite, TF.js) tienen la misma lista de etiquetas que el modelo del servidor.
- Cobertura mínima: 80 % de líneas en `domain`, `application`, `agents` y `mcp_server`. El pipeline falla si baja.
- Ruff y mypy sin errores en el pipeline.
- Ninguna tarea se da por terminada con tests fallando.

## 9. Seguridad [común]

- Toda ruta, excepto `/salud` y la documentación OpenAPI, exige un JWT emitido por Keycloak.
- Se validan firma (JWKS de Keycloak), emisor (`iss`), audiencia (`aud`) y vigencia (`exp`) en cada solicitud (RNF-02).
- Los permisos se verifican en el servidor, nunca solo en el frontend (RN-16). Roles: `administrador`, `tecnico_campo`, `gerencia`, más cuentas de servicio por cliente (n8n, `servicio-ia`, GraphQL, otros microservicios). Un usuario puede tener más de un rol.
- El servicio no gestiona contraseñas ni credenciales de usuario; eso es exclusivo de Keycloak.
- Secretos y configuración solo por variables de entorno o gestor de secretos; nunca en el repositorio (RNF-03).
- Comunicación externa por HTTPS/TLS; conexión a RabbitMQ por AMQPS (RNF-01), salvo la excepción local indicada en Mensajería.
- Los logs no contienen tokens, secretos ni datos personales más allá del ID de usuario.

**Permisos de este servicio:**

| Operación | Roles |
|---|---|
| Estimar rendimiento, analizar patrones, consultar agentes y solicitar reportes | `gerencia` |
| Clasificar imágenes y descargar modelos para el dispositivo | `tecnico_campo` |
| Publicar una nueva versión de modelo | `administrador` |
| Solicitar reportes programados | cuenta de servicio de n8n |
| Lectura de resultados para integración | cuentas de servicio autorizadas |

## 10. Mensajería [común]

- Broker: RabbitMQ sobre AMQPS. Solo en desarrollo local y tests con contenedores se permite AMQP sin TLS, dentro de la red de Docker.
- Los comandos van a la cola del servicio destino; los eventos se publican en un exchange de tipo topic con routing key `<servicio>.<entidad>.<evento>` (por ejemplo, `inventario.stock.bajo`).
- Todo mensaje usa este sobre:

```json
{
  "idMensaje": "uuid",
  "idCorrelacion": "uuid (el idSaga en mensajes de Saga)",
  "tipo": "ReporteCompletado",
  "version": 1,
  "fechaOcurrencia": "2026-10-31T12:00:00Z",
  "origen": "servicio-ia",
  "datos": {}
}
```

- Todo consumidor es idempotente por `idMensaje` (y por `idSaga` en comandos de Saga).
- Un mensaje que falla se reintenta 3 veces con espera creciente y luego va a una Dead Letter Queue (RNF-11). Nunca se descarta en silencio.
- Un cambio incompatible en un mensaje incrementa `version`; los consumidores aceptan la versión anterior mientras dure la transición.

## 11. Errores y observabilidad [común]

- Toda respuesta de error usa este formato:

```json
{
  "codigo": "MODELO_NO_DISPONIBLE",
  "mensaje": "El modelo solicitado no está disponible en este momento.",
  "detalles": [],
  "idCorrelacion": "uuid"
}
```

- `codigo` en mayúsculas con guion bajo, estable y documentado en OpenAPI. `mensaje` apto para mostrar al usuario.
- Códigos HTTP: 400 validación · 401 sin autenticación · 403 sin permiso · 404 no encontrado · 409 conflicto o duplicado · 422 regla de negocio violada.
- Logs estructurados en JSON con `idCorrelacion`. El header `X-Correlation-Id` se recibe del Gateway (o se genera si falta) y se propaga a respuestas y mensajes (RNF-22).
- Endpoint `/salud` con liveness y readiness (incluye Firestore, RabbitMQ y modelos cargados; Ollama se informa aparte sin marcar el servicio como caído).
- La caída de otro microservicio no impide que este siga atendiendo sus propias operaciones (RNF-08).

## 12. Simplicidad

- No se construye nada que no esté en una spec.
- Cada dependencia nueva se justifica en el plan.
- Sin abstracciones "por si acaso": un puerto existe porque hay al menos un adaptador real que lo implementa.
- No se agregan modelos, agentes o herramientas MCP que no respondan a un caso de uso.

## 13. Convenciones [común]

- Todo nombre se escribe en español y sin tildes ni ñ (`Campania`, `Danio`): archivos, clases, interfaces, tipos, métodos, variables, rutas, campos JSON, tablas, columnas, colecciones, valores de enumeraciones, códigos de error, tipos de mensaje, routing keys y nombres de servicio.
- Estilo de escritura:
  - Clases, interfaces y tipos en PascalCase (`CostoCampania`).
  - Métodos, variables y campos JSON en camelCase (`fechaInicio`, `cambiarEstado()`). En Python el código usa snake_case (`fecha_inicio`), pero el JSON expuesto sigue en camelCase.
  - Tablas y columnas en snake_case (`costo_campania`, `fecha_inicio`).
  - Rutas en minúsculas, con guiones y recursos en plural (`/api/gestion/v1/campanias/{id}/costos`).
  - Valores de enumeraciones y códigos de error en mayúsculas con guion bajo (`EN_CURSO`, `STOCK_INSUFICIENTE`).
  - Routing keys en minúsculas separadas por puntos (`inventario.stock.bajo`).
- Excepciones, que se quedan en inglés:
  - Carpetas (`domain`, `application`, `adapters`, `infrastructure`…).
  - Archivos y nombres impuestos por frameworks o herramientas (`pom.xml`, `main.ts`, `app.module.ts`, `application.yml`, `routes/api.php`, `main.py`, `__init__.py`, `pyproject.toml`, `Dockerfile`, métodos derivados de Spring Data como `findByEstado`).
  - Headers HTTP estándar (`Authorization`, `X-Correlation-Id`) y claims de JWT (`sub`, `iss`, `aud`, `exp`).
  - Términos técnicos sin traducción habitual (`stock`, `token`, `saga`, `items`).
- Documentación, specs y mensajes al usuario en español.
- Commits con Conventional Commits (tipo en inglés, descripción en español).
- Fechas y horas en ISO 8601 UTC. Las fechas sin hora (por ejemplo, inicio y fin de campaña) se expresan como `AAAA-MM-DD` (`LocalDate` en Java).
- Los valores decimales (montos, cantidades, superficies, producción) se transmiten en JSON, tanto en REST como en mensajes, como texto con punto decimal y sin separador de miles (`"820.50"`); nunca como número JSON, para no perder precisión entre lenguajes.
- El sistema vive en un solo repositorio. Cada microservicio tiene su propio pipeline en GitHub Actions: build, tests e imagen Docker (RNF-20). Cada pipeline está en `.github/workflows/<servicio>.yml`, en la raíz, y se filtra por `servicios/<servicio>/**`.
- Todo el sistema se levanta en local con Docker Compose (RNF-19).

### Glosario de este servicio

| Concepto | Clase / archivo | Ruta REST | Colección |
|---|---|---|---|
| Predicción de rendimiento | `PrediccionRendimiento` | `/predicciones` | `predicciones` |
| Agrupación y anomalía | `Agrupacion`, `Anomalia` | `/analisis` | `analisis` |
| Clasificación de imagen | `ClasificacionImagen` | `/clasificaciones` | `clasificaciones` |
| Consulta a agente | — | `/consultas-agente` | `trabajos` |
| Reporte | `Reporte` | `/reportes` | `trabajos` |
| Trabajo asíncrono | — | `/trabajos/{id}` | `trabajos` |
| Versión de modelo | `VersionModelo` | `/modelos` | `versiones_modelo` |

| Enumeración | Valores |
|---|---|
| `EstadoTrabajo` | `EN_COLA` / `PROCESANDO` / `COMPLETADO` / `FALLIDO` |
| Formato de reporte | `PDF` / `XLSX` |

## Enmiendas

- Versión: 2.3.0 (2026-11-01)
- Cambiar una regla requiere actualizar este documento, registrar el motivo y subir la versión:
  - MAJOR: se elimina o redefine una regla.
  - MINOR: se agrega una regla.
  - PATCH: aclaraciones de redacción sin cambio de significado.
- Un cambio en una sección **[común]** se aplica a los cuatro microservicios en la misma versión.

| Versión | Fecha | Motivo |
|---|---|---|
| 1.0.0 | 2026-10-31 | Versión inicial. |
| 2.0.0 | 2026-11-01 | Todo nombre pasa a español (rutas, campos, enumeraciones, códigos de error, mensajes, eventos y servicios). Rutas con prefijo de servicio y versión (`/api/<servicio>/v1/...`). Servicios renombrados a `servicio-*`. Health check en `/salud`. |
| 2.1.0 | 2026-11-01 | **[común]** Decimales como texto en JSON (REST y mensajes); fechas sin hora como `AAAA-MM-DD` en los cuatro servicios; la tabla de permisos y el glosario son propios de cada servicio. Sin cambios propios. Nota: los históricos que recibe de `servicio-gestion` traen montos, superficie y producción como texto; se convierten a decimal antes de usarlos. |
| 2.3.0 | 2026-11-01 | **[común]** El sistema vive en un solo repositorio: cada pipeline está en `.github/workflows/<servicio>.yml`, en la raíz, y se filtra por `servicios/<servicio>/**`. Se permite AMQP sin TLS solo en desarrollo local y tests con contenedores. Los cuatro servicios quedan en la misma versión. Sin cambios propios. |
