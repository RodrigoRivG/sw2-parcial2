#!/usr/bin/env python3
"""Preflight de servicios administrados; sin consultar cuentas ni imprimir secretos."""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'despliegue'))
from configuracion import completar_urls, leer


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('destino', choices=['aws', 'azure', 'gcp', 'compartidos'])
    p.add_argument('--archivo', type=Path, help='Configuración completa alternativa para pruebas')
    p.add_argument('--nube', choices=['azure', 'aws', 'gcp'], default='azure', help='Destino del componente compartido')
    args = p.parse_args()
    comunes = leer(RAIZ / '.env.despliegue.compartidos')
    v = leer(args.archivo) if args.archivo else {**comunes, **(leer(RAIZ / f'.env.despliegue.{args.destino}') if args.destino != 'compartidos' else {})}
    if args.destino == 'compartidos' and not args.archivo:
        v.update(leer(RAIZ / f'.env.despliegue.{args.nube}'))
    v = completar_urls(args.nube if args.destino == 'compartidos' else args.destino, v)
    errores = []

    def exigir(k):
        x = v.get(k, '')
        if not x or any(t in x for t in ['.example', 'REEMPLAZAR', 'PENDIENTE']):
            errores.append('Completar ' + k)

    def https(k):
        exigir(k)
        u = urlparse(v.get(k, ''))
        if u.scheme != 'https' or not u.hostname:
            errores.append(k + ' debe ser una URL HTTPS')

    for k in ['KEYCLOAK_ISSUER', 'KEYCLOAK_JWKS_URI', 'KEYCLOAK_TOKEN_URL']:
        https(k)
    issuer = v.get('KEYCLOAK_ISSUER', '')
    if not issuer.endswith('/realms/agro'):
        errores.append('KEYCLOAK_ISSUER debe terminar en /realms/agro')
    for k, sufijo in [('KEYCLOAK_JWKS_URI', '/protocol/openid-connect/certs'), ('KEYCLOAK_TOKEN_URL', '/protocol/openid-connect/token')]:
        if v.get(k) != issuer + sufijo: errores.append(k + ' debe corresponder al mismo issuer')
    for k in ['RABBITMQ_HOST', 'RABBITMQ_USER', 'RABBITMQ_PASSWORD', 'OPERACIONES_CLIENT_SECRET', 'AWS_BUCKET', 'APP_KEY']:
        exigir(k)
    if v.get('RABBITMQ_SSL') != 'true': errores.append('RABBITMQ_SSL debe ser true')
    if bool(v.get('AWS_ACCESS_KEY_ID')) != bool(v.get('AWS_SECRET_ACCESS_KEY')):
        errores.append('Completar ambas credenciales AWS o usar el rol IAM de AWS')
    if args.destino != 'aws':
        exigir('AWS_ACCESS_KEY_ID'); exigir('AWS_SECRET_ACCESS_KEY')
    origenes = [s.strip().rstrip('/') for s in v.get('CORS_ORIGENES_PERMITIDOS', '').split(',') if s.strip()]
    exigir('CORS_ORIGENES_PERMITIDOS')
    if not origenes or any(urlparse(s).scheme != 'https' or not urlparse(s).hostname or urlparse(s).path or '*' in s for s in origenes):
        errores.append('CORS requiere orígenes HTTPS sin rutas ni comodines')
    if args.destino == 'compartidos':
        for k in ['KC_DB_URL', 'KC_DB_USERNAME', 'KC_DB_PASSWORD', 'KC_BOOTSTRAP_ADMIN_USERNAME', 'KC_BOOTSTRAP_ADMIN_PASSWORD', 'IA_CLIENT_SECRET', 'GRAPHQL_CLIENT_SECRET', 'N8N_CLIENT_SECRET', 'KEYCLOAK_CLAVE_USUARIOS_PRUEBA', 'N8N_ENCRYPTION_KEY', 'FIREBASE_PROYECTO_ID', 'N8N_DB_HOST', 'N8N_DB_USER', 'N8N_DB_PASSWORD']:
            exigir(k)
        https('N8N_PUBLIC_URL'); https('API_GATEWAY_URL')
        if 'sslmode=require' not in v.get('KC_DB_URL', ''): errores.append('KC_DB_URL requiere sslmode=require')
        archivos = [('FIREBASE_CREDENCIALES_ARCHIVO', './secretos/firebase-cuenta-servicio.json')]
        ruta = RAIZ / 'despliegue/generado/realm-agro.json'
        if not ruta.is_file(): errores.append('Ejecutar preparar-despliegue.py para preparar el realm')
        else:
            realm = json.loads(ruta.read_text())
            web = next(c for c in realm['clients'] if c['clientId'] == 'agro-web')
            if web['webOrigins'] != origenes: errores.append('Regenerar realm después de cambiar CORS')
    else:
        for k in ['API_GATEWAY_URL', 'GESTION_URL', 'INVENTARIO_URL', 'OPERACIONES_URL', 'IA_URL', 'GRAPHQL_URL']:
            https(k)
        for k in ['SPRING_DATASOURCE_URL', 'SPRING_DATASOURCE_USERNAME', 'SPRING_DATASOURCE_PASSWORD', 'MONGODB_URI', 'RABBITMQ_URL', 'IA_CLIENT_SECRET', 'GRAPHQL_CLIENT_SECRET', 'IMAGEN_PREFIJO', 'IMAGEN_ETIQUETA']:
            exigir(k)
        if v.get('NUBE') != args.destino: errores.append('NUBE no coincide con el destino')
        if args.destino == 'azure' and v.get('CONSUMIDORES_ACTIVOS', 'true') != 'true':
            errores.append('El primer despliegue Azure necesita CONSUMIDORES_ACTIVOS=true')
        if not v.get('RABBITMQ_URL', '').startswith('amqps://'): errores.append('RABBITMQ_URL requiere amqps://')
        if not v.get('MONGODB_URI', '').startswith('mongodb+srv://'): errores.append('MONGODB_URI requiere la URI SRV de Atlas')
        if 'sslmode=require' not in v.get('SPRING_DATASOURCE_URL', ''): errores.append('PostgreSQL requiere sslmode=require')
        archivos = []
        if args.destino == 'gcp':
            for k in ['GCP_REGION', 'GCP_SERVICE_ACCOUNT_EMAIL', 'KEYCLOAK_IMAGEN', 'N8N_IMAGEN']: exigir(k)
            if '.pkg.dev/' not in v.get('IMAGEN_PREFIJO', ''): errores.append('IMAGEN_PREFIJO de GCP debe apuntar a Artifact Registry')
        elif args.destino == 'azure':
            for k in ['AZURE_LOCATION', 'AZURE_ENVIRONMENT_ID', 'AZURE_IDENTITY_ID', 'AZURE_KEYVAULT_URL', 'KEYCLOAK_IMAGEN', 'N8N_IMAGEN']: exigir(k)
            if '.azurecr.io' not in v.get('IMAGEN_PREFIJO', ''): errores.append('IMAGEN_PREFIJO de Azure debe apuntar a ACR')
        else:
            for k in ['AWS_ACCOUNT_ID', 'AWS_APP_RUNNER_ECR_ROLE_ARN', 'AWS_APP_RUNNER_INSTANCE_ROLE_ARN', 'AWS_APP_RUNNER_AUTOSCALING_ARN']: exigir(k)
            if '.dkr.ecr.' not in v.get('IMAGEN_PREFIJO', ''): errores.append('IMAGEN_PREFIJO de AWS debe apuntar a ECR')
            if v.get('AWS_APP_RUNNER_HABILITADO') != 'true':
                errores.append('Confirmar acceso existente a App Runner: AWS_APP_RUNNER_HABILITADO=true; cerrado a clientes nuevos desde 2026-04-30')
    for k, defecto in archivos:
        ruta = Path(v.get(k) or defecto)
        if not ruta.is_absolute(): ruta = RAIZ / 'despliegue' / ruta
        if not ruta.is_file(): errores.append('Falta archivo indicado por ' + k)
    if errores:
        print('Configuración pendiente (sin valores de secretos):')
        for e in dict.fromkeys(errores): print('- ' + e)
        raise SystemExit(1)
    print(args.destino + ': preflight completo; permisos, conectividad y cuotas cloud deben comprobarse en la cuenta.')


if __name__ == '__main__':
    main()
