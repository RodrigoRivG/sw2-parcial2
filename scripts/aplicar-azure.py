#!/usr/bin/env python3
"""Aplicación manual/CI de manifiestos Azure ya validados; crea o actualiza recursos."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'despliegue'))
from configuracion import leer


def ejecutar(*args):
    subprocess.run(['az', *args, '--only-show-errors', '--output', 'none'], check=True)


ORDEN = ['keycloak', 'servicio-gestion', 'servicio-inventario', 'servicio-operaciones', 'servicio-ia', 'graphql-server', 'api-gateway', 'n8n', 'operaciones-consumidor', 'operaciones-programador']


def consultar(*args):
    resultado = subprocess.run(['az', *args, '--only-show-errors', '--output', 'json'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if resultado.returncode:
        raise SystemExit('No se pudo consultar Azure: ' + ' '.join(args[:3]) + '. Revisar acceso y recursos.')
    return json.loads(resultado.stdout)


def comprobar(v, carpeta, grupo):
    entorno_id = v['AZURE_ENVIRONMENT_ID']
    # El YAML actual de Azure CLI usa environmentId; managedEnvironmentId se descarta.
    # Validar TODOS los manifiestos antes de cargar secretos o crear la primera app.
    for nombre in ORDEN:
        archivo = carpeta / (nombre + '.json')
        if not archivo.is_file():
            raise SystemExit('Falta manifiesto: ' + nombre)
        m = json.loads(archivo.read_text())
        if m.get('name') != 'sw2-' + nombre or m.get('properties', {}).get('environmentId') != entorno_id:
            raise SystemExit('Manifiesto con nombre/entorno incorrecto: ' + nombre + '. Regenerar manifiestos.')
        if 'managedEnvironmentId' in m['properties']:
            raise SystemExit('Campo antiguo managedEnvironmentId en ' + nombre)
    entorno = consultar('containerapp', 'env', 'show', '--ids', entorno_id)
    propiedades = entorno.get('properties', {})
    modo = str(propiedades.get('environmentMode') or propiedades.get('mode') or '').lower()
    if modo == 'express':
        raise SystemExit('El entorno configurado es Express; se necesita WorkloadProfiles o ConsumptionOnly para Key Vault e identidades.')
    if propiedades.get('provisioningState', '').lower() != 'succeeded':
        raise SystemExit('El entorno de Container Apps no está en Succeeded.')
    if propiedades.get('defaultDomain') != v.get('AZURE_ENVIRONMENT_DOMAIN'):
        raise SystemExit('El dominio configurado no coincide con el entorno Azure. Actualizar AZURE_DEPLOY_ENV.')
    existentes = {}
    for nombre in ORDEN:
        resultado = subprocess.run(['az', 'containerapp', 'show', '--resource-group', grupo,
                                    '--name', 'sw2-' + nombre, '--only-show-errors', '--output', 'json'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if resultado.returncode:
            error = resultado.stderr.lower()
            if not any(marca in error for marca in (b'not found', b'could not be found', b'resourcenotfound')):
                raise SystemExit('No se pudo consultar Container App ' + nombre + '; revisar permisos y grupo.')
            existentes[nombre] = False
        else:
            app = json.loads(resultado.stdout)
            propiedades_app = app.get('properties', {})
            actual = propiedades_app.get('environmentId') or propiedades_app.get('managedEnvironmentId')
            if not actual or actual.lower() != entorno_id.lower():
                raise SystemExit('La app sw2-' + nombre + ' pertenece a otro entorno. No se modifica ni borra automáticamente.')
            existentes[nombre] = True
    print('Azure comprobado: entorno, dominio, manifiestos y destino de las diez aplicaciones.', flush=True)
    return existentes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--grupo', required=True)
    p.add_argument('--solo-comprobar', action='store_true', help='Lecturas cloud; no carga secretos ni crea aplicaciones')
    args = p.parse_args()
    for destino in ['azure', 'compartidos']:
        subprocess.run([sys.executable, str(RAIZ / 'scripts/validar-despliegue.py'), destino, '--nube', 'azure'], check=True)
    v = {**leer(RAIZ / '.env.despliegue.compartidos'), **leer(RAIZ / '.env.despliegue.azure')}
    carpeta = RAIZ / 'despliegue/generado/listo/azure'
    secretos = json.loads((carpeta / 'secretos.json').read_text())
    if any(not x for x in secretos.values()):
        raise SystemExit('Hay secretos vacíos; no se aplicó el despliegue.')
    existentes = comprobar(v, carpeta, args.grupo)
    if args.solo_comprobar:
        return
    vault = v['AZURE_KEYVAULT_URL'].rstrip('/').split('//', 1)[1].split('.')[0]
    with tempfile.TemporaryDirectory(prefix='sw2-secretos-') as temporal:
        for nombre, valor in secretos.items():
            archivo = Path(temporal) / nombre
            archivo.write_text(valor)
            archivo.chmod(0o600)
            ejecutar('keyvault', 'secret', 'set', '--vault-name', vault, '--name', nombre, '--file', str(archivo))
    # Procesos de fondo al final. No se crean bases ni se borran datos aquí.
    for nombre in ORDEN:
        archivo = carpeta / (nombre + '.json')
        if existentes[nombre]:
            ejecutar('containerapp', 'update', '--resource-group', args.grupo, '--name', 'sw2-' + nombre, '--yaml', str(archivo))
        else:
            ejecutar('containerapp', 'create', '--resource-group', args.grupo, '--name', 'sw2-' + nombre,
                     '--environment', v['AZURE_ENVIRONMENT_ID'], '--yaml', str(archivo))
        print('Aplicado: ' + nombre, flush=True)


if __name__ == '__main__':
    main()
