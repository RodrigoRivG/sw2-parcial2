#!/usr/bin/env python3
"""Genera archivos privados sin leer .env ni sobrescribir configuración existente."""

import base64
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil

RAIZ = Path(__file__).resolve().parents[1]


def leer(ruta: Path) -> dict[str, str]:
    valores = {}
    for linea in ruta.read_text().splitlines():
        if linea.strip() and not linea.lstrip().startswith('#') and '=' in linea:
            clave, valor = linea.split('=', 1)
            valor = valor.strip()
            if len(valor) >= 2 and valor[0] in "\"'" and valor[-1] == valor[0]:
                valor = valor[1:-1]
            valores[clave.strip()] = valor
    return valores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nube', choices=['azure', 'aws', 'gcp'], default='azure')
    args = parser.parse_args()
    plantilla = leer(RAIZ / '.env.despliegue.example')
    central = RAIZ / '.env.despliegue.compartidos'
    configuracion = leer(central) if central.exists() else plantilla.copy()
    claves = [
        'OPERACIONES_CLIENT_SECRET', 'IA_CLIENT_SECRET', 'GRAPHQL_CLIENT_SECRET',
        'N8N_CLIENT_SECRET', 'N8N_ENCRYPTION_KEY', 'KC_BOOTSTRAP_ADMIN_PASSWORD',
        'KEYCLOAK_CLAVE_USUARIOS_PRUEBA',
    ]
    if not central.exists():
        for clave in claves:
            configuracion[clave] = secrets.token_hex(32)
        configuracion['APP_KEY'] = 'base64:' + base64.b64encode(secrets.token_bytes(32)).decode()
        configuracion['KC_BOOTSTRAP_ADMIN_USERNAME'] = 'admin'
        configuracion['API_GATEWAY_URL'] = 'https://api-azure.example'

    for destino in ['compartidos', 'aws', 'azure', 'gcp']:
        archivo = RAIZ / f'.env.despliegue.{destino}'
        if archivo.exists():
            print(f'Conservado: {archivo.name}')
            continue
        if destino == 'compartidos':
            valores = {**plantilla, **configuracion}
            valores['NUBE'] = 'azure'
            valores['API_DOMAIN'] = 'api-azure.example'
            valores['TRABAJOS_CONSUMIDOR_ACTIVO'] = 'false'
        else:
            valores = {
                'NUBE': destino,
                'API_GATEWAY_URL': f'https://api-{destino}.example',
                **{k: f'https://{s}-{destino}.example' for k, s in [('GESTION_URL', 'gestion'), ('INVENTARIO_URL', 'inventario'), ('OPERACIONES_URL', 'operaciones'), ('IA_URL', 'ia'), ('GRAPHQL_URL', 'graphql')]},
                'IMAGEN_PREFIJO': 'REGISTRO_PENDIENTE/sw2',
                'CONSUMIDORES_ACTIVOS': 'true' if destino == 'azure' else 'false',
                'TRABAJOS_CONSUMIDOR_ACTIVO': 'true' if destino == 'azure' else 'false',
            }
            campos = {
                'aws': ['AWS_APP_RUNNER_HABILITADO', 'AWS_ACCOUNT_ID', 'AWS_APP_RUNNER_ECR_ROLE_ARN', 'AWS_APP_RUNNER_INSTANCE_ROLE_ARN', 'AWS_APP_RUNNER_AUTOSCALING_ARN'],
                'azure': ['AZURE_LOCATION', 'AZURE_ENVIRONMENT_ID', 'AZURE_IDENTITY_ID', 'AZURE_KEYVAULT_URL'],
                'gcp': ['GCP_REGION', 'GCP_SERVICE_ACCOUNT_EMAIL', 'KEYCLOAK_IMAGEN', 'N8N_IMAGEN'],
            }
            valores.update({k: plantilla[k] for k in campos[destino]})
        # Cada contenedor recibe solo sus variables mediante environment/secrets.
        contenido = '# PRIVADO. No versionar. Completar valores externos antes de iniciar.\n'
        contenido += '\n'.join(f'{k}={v}' for k, v in valores.items()) + '\n'
        descriptor = os.open(archivo, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as salida:
            salida.write(contenido)
        print(f'Creado: {archivo.name} (permisos 600)')

    central_config = leer(central)
    central_config.update(leer(RAIZ / f'.env.despliegue.{args.nube}'))
    origenes = [s.strip().rstrip('/') for s in central_config['CORS_ORIGENES_PERMITIDOS'].split(',') if s.strip()]
    if not origenes or any(not s.startswith('https://') or '*' in s for s in origenes):
        raise SystemExit('CORS_ORIGENES_PERMITIDOS requiere orígenes HTTPS explícitos.')
    realm = json.loads((RAIZ / 'docker/keycloak/realms/realm-agro.json').read_text())
    realm['clients'] = [c for c in realm['clients'] if c['clientId'] != 'agro-pruebas']
    web = next(c for c in realm['clients'] if c['clientId'] == 'agro-web')
    web['webOrigins'] = origenes
    web['redirectUris'] = [origen + '/*' for origen in origenes]
    web['attributes']['post.logout.redirect.uris'] = '##'.join(web['redirectUris'])
    realm['sslRequired'] = 'all'
    generado = RAIZ / 'despliegue/generado'
    generado.mkdir(exist_ok=True)
    (generado / 'realm-agro.json').write_text(json.dumps(realm, ensure_ascii=False, indent=2) + '\n')
    contexto = generado / 'keycloak'
    contexto.mkdir(exist_ok=True)
    shutil.copyfile(generado / 'realm-agro.json', contexto / 'realm-agro.json')
    shutil.copytree(RAIZ / 'docker/keycloak/temas', contexto / 'temas', dirs_exist_ok=True)
    print('Realm de despliegue preparado; el realm local no se modificó.')
    print('Secretos generados sin mostrarlos. Faltan endpoints y credenciales externos.')


if __name__ == '__main__':
    main()
