# Azure desde GitHub

## Qué queda preparado

Un solo código y un workflow: `.github/workflows/desplegar-azure.yml`.
No se necesita una rama permanente por nube. El workflow utiliza el commit de la
rama seleccionada y lo etiqueta con su SHA.

- `validar` (predeterminado): pruebas de configuración; sin credenciales, imágenes
  ni recursos de Azure. También se ejecuta en PR que cambie esta base.
- `desplegar` (manual): lee el GitHub Environment `azure`, valida los valores,
  inicia sesión por OIDC, construye las ocho imágenes en el runner, las publica
  en ACR y aplica las Container Apps.
- `apagar` / `encender` (manual): réplicas mínimas a 0 o de vuelta a 1 en los
  procesos continuos. Usar `apagar` entre sesiones de prueba para cuidar créditos.

Las imágenes se construyen en el runner de GitHub porque ACR Tasks (`az acr build`)
no está habilitado en suscripciones con créditos gratuitos como Azure for Students.

## 1. Infraestructura base (una vez)

`scripts/infra-azure.sh` es idempotente y crea en el grupo `sw2-azure`
(región `brazilsouth` por defecto):

- Container Registry Basic, Key Vault (RBAC) y Container Apps Environment sin
  Log Analytics (los logs se ven con `az containerapp logs show --follow`).
- Identidad `sw2-apps` (AcrPull y lectura del vault) usada por los contenedores.
- Identidad `sw2-github` con credencial federada para
  `repo:<repo>:environment:azure`; no requiere app registration en Entra ID.
- PostgreSQL Flexible B1ms de 32 GB (servicios gratuitos de la cuenta) con
  `gestion_db`, `keycloak_azure` y `n8n_db`, accesible desde servicios de Azure.

```bash
az login                       # o usar Azure Cloud Shell con el repo clonado
bash scripts/infra-azure.sh    # REGION=<otra> si la política de la cuenta la rechaza
```

Escribe `despliegue/secretos/azure-infra.env` (privado) y
`despliegue/secretos/azure-github.txt` (variables del Environment). Para borrar
todo al terminar la evaluación: `az group delete -n sw2-azure --yes`.

## 2. Configuración

```bash
python3 scripts/preparar-despliegue.py --nube azure   # genera claves internas una vez
cat .env.despliegue.compartidos despliegue/secretos/azure-infra.env > despliegue/secretos/AZURE_DEPLOY_ENV.env
```

Completar en ese archivo lo externo: MongoDB Atlas, RabbitMQ, AWS (DynamoDB/S3),
Firebase, `CORS_ORIGENES_PERMITIDOS` (URL HTTPS del frontend)
y `OLLAMA_BASE_URL` (túnel hacia la máquina con Qwen). Las URL de Gateway,
servicios, Keycloak y n8n se deducen de `AZURE_ENVIRONMENT_DOMAIN`.
Atlas debe permitir el acceso desde `0.0.0.0/0`, porque Container Apps no tiene una IP de salida fija.

## 3. GitHub Environment `azure`

Crear el Environment en GitHub y restringirlo a las ramas autorizadas.

- Variables: copiar las seis de `azure-github.txt` (`AZURE_CLIENT_ID`,
  `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`,
  `AZURE_REGISTRY_NAME`, `AZURE_REGISTRY_LOGIN_SERVER`).
- Secrets: `AZURE_DEPLOY_ENV` (contenido de `AZURE_DEPLOY_ENV.env`),
  `FIREBASE_SERVICE_ACCOUNT_JSON` (cuenta FCM de n8n).

No pegar secretos en issues, archivos versionados ni mensajes de chat.
El workflow fija el registro, el SHA y la activación de consumidores.

## URL y primer arranque

Cada servicio recibe la URL HTTPS de su Container App, `https://sw2-<app>.<dominio>`,
deducida de `AZURE_ENVIRONMENT_DOMAIN`; el dominio existe desde que se crea el
Environment, antes de la primera app. El validador rechaza lo que siga en `.example`.
Gateway apunta a las URL Azure de los servicios y GraphQL; todos usan la URL
Azure de Keycloak y el Gateway Azure. Configurar los orígenes HTTPS reales del
frontend en CORS y regenerar su realm antes de construir la imagen de Keycloak.
Keycloak solo importa un realm nuevo: los cambios posteriores se aplican por su
administración, sin borrar usuarios.

El repositorio del frontend es independiente y no está dentro de este backend.
Su despliegue debe hacerse también en Azure y configurar los endpoints de este
backend; esta base no simula haber desplegado el frontend.

## Orden y comprobaciones

1. Completar recursos, acceso de red, secretos y endpoints.
2. Publicar la rama de preparación y ejecutar `validar` en GitHub Actions.
3. Ejecutar manualmente `desplegar` cuando se tengan las credenciales.
4. Comprobar login, salud/readiness, Saga, fotos, modelos, GraphQL y push.
5. Ejecutar los entrenamientos en la nube y publicar sus modelos.
6. Conectar Ollama local al final.

El workflow no crea tablas DynamoDB ni entrena modelos. Esas inicializaciones
se realizarán una vez con los permisos correspondientes, no en cada arranque.
No afirmar que todo está funcionando hasta pasar las comprobaciones reales.
El mínimo uno de consumidores, Keycloak y n8n consume créditos aun sin tráfico.

Referencias: [OIDC desde GitHub](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect),
[secretos en Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets).

## Acceso de IA a Atlas y S3

IA reutiliza `MONGODB_URI`, pero selecciona `MONGODB_BASE=ia_db`. El usuario de
Atlas necesita `readWrite` en `ia_db`, además de `inventario_db`.
El bucket existente se reutiliza con `S3_PREFIJO=ia/`. Las rutas lógicas guardadas
siguen siendo `modelos/...`, `reportes/...`, `datasets/...` y `temporales/...`.
No se requieren credenciales Google para IA; la cuenta Firebase sigue siendo de n8n.

Agregar a la política IAM del usuario AWS (reemplazar `BUCKET`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::BUCKET/ia/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::BUCKET",
      "Condition": {"StringLike": {"s3:prefix": ["ia/*"]}}
    }
  ]
}
```

Conservar los permisos de DynamoDB y `incidencias/*`. El permiso `ListBucket`
es necesario para que S3 devuelva `404` en las lecturas de objetos inexistentes.
Las pruebas usan bases `pruebas-*` y prefijos aislados en LocalStack, nunca los
recursos reales. TTL y reglas de ciclo de vida quedan fuera de esta entrega.
