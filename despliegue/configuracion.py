"""Modelo de ejecución compartido por los generadores de manifiestos administrados."""
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def leer(ruta):
    valores = {}
    if not ruta.is_file():
        return valores
    for linea in ruta.read_text().splitlines():
        if linea.strip() and not linea.lstrip().startswith('#') and '=' in linea:
            clave, valor = linea.split('=', 1)
            valor = valor.strip()
            if len(valor) >= 2 and valor[0] in "\"'" and valor[-1] == valor[0]:
                valor = valor[1:-1]
            valores[clave.strip()] = valor
    return valores


@dataclass
class Secreto:
    nombre: str
    valor: str


MARCAS_PENDIENTES = ('.example', 'REEMPLAZAR', 'PENDIENTE')


def pendiente(valor):
    return not valor or any(t in valor for t in MARCAS_PENDIENTES)


# En Container Apps la URL externa es https://<app>.<dominio del entorno>.
URLS_AZURE = {'API_GATEWAY_URL': 'api-gateway', 'GESTION_URL': 'servicio-gestion', 'INVENTARIO_URL': 'servicio-inventario', 'OPERACIONES_URL': 'servicio-operaciones', 'IA_URL': 'servicio-ia', 'GRAPHQL_URL': 'graphql-server', 'N8N_PUBLIC_URL': 'n8n'}


def completar_urls(nube, v):
    """Deduce las URL de Azure a partir de AZURE_ENVIRONMENT_DOMAIN; respeta las ya definidas."""
    dominio = v.get('AZURE_ENVIRONMENT_DOMAIN', '')
    if nube != 'azure' or pendiente(dominio):
        return v
    r = dict(v)
    for clave, app in URLS_AZURE.items():
        if pendiente(r.get(clave, '')):
            r[clave] = f'https://sw2-{app}.{dominio}'
    if pendiente(r.get('KEYCLOAK_ISSUER', '')):
        r['KEYCLOAK_ISSUER'] = f'https://sw2-keycloak.{dominio}/realms/agro'
    for clave, sufijo in [('KEYCLOAK_JWKS_URI', '/protocol/openid-connect/certs'), ('KEYCLOAK_TOKEN_URL', '/protocol/openid-connect/token')]:
        if pendiente(r.get(clave, '')):
            r[clave] = r['KEYCLOAK_ISSUER'] + sufijo
    return r


def servicios(nube, v, comunes):
    def val(k, defecto=''):
        return v.get(k) or defecto

    def sec(k):
        return Secreto(k.lower().replace('_', '-'), val(k))

    activo = val('CONSUMIDORES_ACTIVOS', 'true' if nube == 'azure' else 'false') == 'true'
    auth = {k: val(k) for k in ['KEYCLOAK_ISSUER', 'KEYCLOAK_JWKS_URI']}
    token = {'KEYCLOAK_TOKEN_URL': val('KEYCLOAK_TOKEN_URL'), 'API_GATEWAY_URL': val('API_GATEWAY_URL')}
    rabbit = {k: val(k, d) for k, d in [('RABBITMQ_HOST', ''), ('RABBITMQ_PORT', '5671'), ('RABBITMQ_VHOST', '/')]}
    rabbit.update(RABBITMQ_USER=sec('RABBITMQ_USER'), RABBITMQ_PASSWORD=sec('RABBITMQ_PASSWORD'), RABBITMQ_SSL='true')
    ops = {**auth, **token, **rabbit, 'KEYCLOAK_AUDIENCE': 'servicio-operaciones', 'KEYCLOAK_CLIENT_ID': 'servicio-operaciones', 'KEYCLOAK_CLIENT_SECRET': sec('OPERACIONES_CLIENT_SECRET'), 'AWS_DEFAULT_REGION': val('AWS_DEFAULT_REGION', 'us-east-1'), 'AWS_BUCKET': val('AWS_BUCKET'), 'DYNAMODB_PREFIJO_TABLAS': val('DYNAMODB_PREFIJO_TABLAS'), 'APP_ENV': 'production', 'APP_DEBUG': 'false', 'APP_KEY': sec('APP_KEY'), 'CACHE_STORE': 'file', 'SESSION_DRIVER': 'file', 'QUEUE_CONNECTION': 'sync', 'LOG_CHANNEL': 'stderr'}
    for k in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']:
        if val(k): ops[k] = sec(k)
    resultado = {}

    def agregar(nombre, env, puerto, memoria=1024, cpu=1, continuo=False, imagen=None, comando=None):
        resultado[nombre] = {'env': env, 'puerto': puerto, 'memoria': memoria, 'cpu': cpu, 'continuo': continuo, 'imagen': imagen or val('IMAGEN_PREFIJO', 'REGISTRO_PENDIENTE/sw2') + '/' + nombre + ':' + val('IMAGEN_ETIQUETA', 'verificacion')}
        if comando: resultado[nombre]['comando'] = comando

    agregar('servicio-gestion', {**auth, 'KEYCLOAK_AUDIENCE': 'servicio-gestion', 'SERVER_PORT': '8080', 'JAVA_TOOL_OPTIONS': '-Xmx384m', 'SPRING_DATASOURCE_URL': val('SPRING_DATASOURCE_URL'), 'SPRING_DATASOURCE_USERNAME': sec('SPRING_DATASOURCE_USERNAME'), 'SPRING_DATASOURCE_PASSWORD': sec('SPRING_DATASOURCE_PASSWORD'), 'SPRING_RABBITMQ_HOST': val('RABBITMQ_HOST'), 'SPRING_RABBITMQ_PORT': val('RABBITMQ_PORT', '5671'), 'SPRING_RABBITMQ_USERNAME': sec('RABBITMQ_USER'), 'SPRING_RABBITMQ_PASSWORD': sec('RABBITMQ_PASSWORD'), 'SPRING_RABBITMQ_VIRTUAL_HOST': val('RABBITMQ_VHOST', '/'), 'SPRING_RABBITMQ_SSL_ENABLED': 'true', 'SPRING_RABBITMQ_LISTENER_SIMPLE_AUTO_STARTUP': 'true' if activo else 'false'}, 8080, continuo=activo)
    agregar('servicio-inventario', {**auth, 'KEYCLOAK_AUDIENCE': 'servicio-inventario', 'NODE_ENV': 'production', 'PORT': '3000', 'MONGODB_URI': sec('MONGODB_URI'), 'RABBITMQ_URL': sec('RABBITMQ_URL'), 'RABBITMQ_CONSUMIDOR_ACTIVO': 'true' if activo else 'false'}, 3000, continuo=activo)
    agregar('servicio-operaciones', ops, 8080)
    ia = {**auth, **token, 'KEYCLOAK_AUDIENCE': 'servicio-ia', 'KEYCLOAK_CLIENT_ID': 'servicio-ia', 'KEYCLOAK_CLIENT_SECRET': sec('IA_CLIENT_SECRET'), 'PORT': '8080', 'MONGODB_URI': sec('MONGODB_URI'), 'MONGODB_BASE': val('MONGODB_BASE', 'ia_db'), 'AWS_BUCKET': val('AWS_BUCKET'), 'AWS_DEFAULT_REGION': val('AWS_DEFAULT_REGION', 'us-east-1'), 'S3_PREFIJO': val('S3_PREFIJO', 'ia/'), 'RABBITMQ_URL': sec('RABBITMQ_URL'), 'OLLAMA_BASE_URL': val('OLLAMA_BASE_URL', 'http://127.0.0.1:11434'), 'OLLAMA_MODEL': val('OLLAMA_MODEL', 'qwen2.5:7b-instruct-q3_K_M'), 'TRABAJOS_CONSUMIDOR_ACTIVO': 'true' if activo else 'false', 'WHISPER_CARPETA': '/modelos/whisper', 'WHISPER_MODEL': 'small'}
    for k, defecto in [('TRABAJOS_CONCURRENCIA', '2'), ('TRABAJOS_RETENCION_DIAS', '30'), ('MODELOS_INTERVALO_REVISION_SEGUNDOS', '60'), ('VISION_TAMANIO_MAXIMO_IMAGEN_MB', '10'), ('VISION_TAMANIO_MAXIMO_VIDEO_MB', '50'), ('AGENTES_NUM_CTX', '8192'), ('REPORTES_RETENCION_DIAS', '7'), ('REPORTES_TAMANIO_MAXIMO_AUDIO_MB', '10'), ('NIVEL_LOG', 'INFO')]: ia[k] = val(k, defecto)
    for k in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']:
        if val(k): ia[k] = sec(k)
    # Qwen corre en la máquina del usuario: en la nube quedan TensorFlow, Whisper y OpenCV.
    agregar('servicio-ia', ia, 8080, memoria=2048, cpu=1, continuo=activo)
    agregar('graphql-server', {**auth, **token, 'KEYCLOAK_AUDIENCE': 'graphql-server', 'KEYCLOAK_CLIENT_ID': 'graphql-server', 'KEYCLOAK_CLIENT_SECRET': sec('GRAPHQL_CLIENT_SECRET'), 'NODE_ENV': 'production', 'PORT': '4000'}, 4000, memoria=512)
    agregar('api-gateway', {**auth, 'SERVER_PORT': '8080', 'JAVA_TOOL_OPTIONS': '-Xmx384m', **{k: val(k) for k in ['GESTION_URL', 'INVENTARIO_URL', 'OPERACIONES_URL', 'IA_URL', 'GRAPHQL_URL', 'CORS_ORIGENES_PERMITIDOS']}, 'GATEWAY_TIEMPO_LIMITE': '10s', 'GATEWAY_TIEMPO_LIMITE_SINCRONIZACION': '120000'}, 8080)
    if nube == 'azure':
        # Los procesos de Azure usan exclusivamente SU Gateway.
        env = {**ops}
        for nombre, cmd in [('operaciones-programador', ['php', 'artisan', 'schedule:work']), ('operaciones-consumidor', ['php', 'artisan', 'operaciones:consumir-respuestas'])]:
            agregar(nombre, env, None, memoria=512, imagen=resultado['servicio-operaciones']['imagen'], comando=cmd, continuo=True)
    if nube in {'azure', 'gcp', 'aws'}:
        host = val('KEYCLOAK_ISSUER').removesuffix('/realms/agro')
        kc = {'KC_DB': 'postgres', 'KC_DB_URL': val('KC_DB_URL'), 'KC_DB_USERNAME': sec('KC_DB_USERNAME'), 'KC_DB_PASSWORD': sec('KC_DB_PASSWORD'), 'KC_BOOTSTRAP_ADMIN_USERNAME': val('KC_BOOTSTRAP_ADMIN_USERNAME', 'admin'), 'KC_BOOTSTRAP_ADMIN_PASSWORD': sec('KC_BOOTSTRAP_ADMIN_PASSWORD'), 'KC_HOSTNAME': host, 'KC_HTTP_ENABLED': 'true', 'KC_HTTP_PORT': '8080', 'KC_PROXY_HEADERS': 'xforwarded', 'JAVA_OPTS_KC_HEAP': '-Xms128m -Xmx512m'}
        for k in ['OPERACIONES_CLIENT_SECRET', 'IA_CLIENT_SECRET', 'GRAPHQL_CLIENT_SECRET', 'N8N_CLIENT_SECRET', 'KEYCLOAK_CLAVE_USUARIOS_PRUEBA']:
            kc[k] = sec(k)
        agregar('keycloak', kc, 8080, continuo=True, imagen=val('KEYCLOAK_IMAGEN', 'REGISTRO_PENDIENTE/sw2/keycloak:verificacion'))
    if nube == val('N8N_NUBE', 'azure'):
        n8n = {**rabbit, 'KEYCLOAK_TOKEN_URL': val('KEYCLOAK_TOKEN_URL'), 'API_GATEWAY_URL': val('API_GATEWAY_URL'), 'N8N_CLIENT_SECRET': sec('N8N_CLIENT_SECRET'), 'N8N_ENCRYPTION_KEY': sec('N8N_ENCRYPTION_KEY'), 'N8N_BLOCK_ENV_ACCESS_IN_NODE': 'false', 'N8N_PROTOCOL': 'https', 'N8N_PORT': '5678', 'N8N_PROXY_HOPS': '1', 'N8N_EDITOR_BASE_URL': val('N8N_PUBLIC_URL'), 'WEBHOOK_URL': val('N8N_PUBLIC_URL').rstrip('/') + '/', 'GENERIC_TIMEZONE': 'America/La_Paz', 'TZ': 'America/La_Paz', 'NODE_OPTIONS': '--max-old-space-size=640', 'FIREBASE_PROYECTO_ID': val('FIREBASE_PROYECTO_ID'), 'FIREBASE_CUENTA_SERVICIO': '/run/secrets/firebase.json', 'DB_TYPE': 'postgresdb', 'DB_POSTGRESDB_HOST': val('N8N_DB_HOST'), 'DB_POSTGRESDB_PORT': val('N8N_DB_PORT', '5432'), 'DB_POSTGRESDB_DATABASE': val('N8N_DB_NAME', 'n8n_db'), 'DB_POSTGRESDB_USER': sec('N8N_DB_USER'), 'DB_POSTGRESDB_PASSWORD': sec('N8N_DB_PASSWORD'), 'DB_POSTGRESDB_SSL_ENABLED': 'true', 'DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED': 'true'}
        agregar('n8n', n8n, 5678, continuo=True, imagen=val('N8N_IMAGEN', 'REGISTRO_PENDIENTE/sw2/n8n:verificacion'))
    return resultado
