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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--grupo', required=True)
    args = p.parse_args()
    for destino in ['azure', 'compartidos']:
        subprocess.run([sys.executable, str(RAIZ / 'scripts/validar-despliegue.py'), destino, '--nube', 'azure'], check=True)
    v = {**leer(RAIZ / '.env.despliegue.compartidos'), **leer(RAIZ / '.env.despliegue.azure')}
    carpeta = RAIZ / 'despliegue/generado/listo/azure'
    secretos = json.loads((carpeta / 'secretos.json').read_text())
    if any(not x for x in secretos.values()):
        raise SystemExit('Hay secretos vacíos; no se aplicó el despliegue.')
    vault = v['AZURE_KEYVAULT_URL'].rstrip('/').split('//', 1)[1].split('.')[0]
    with tempfile.TemporaryDirectory(prefix='sw2-secretos-') as temporal:
        for nombre, valor in secretos.items():
            archivo = Path(temporal) / nombre
            archivo.write_text(valor)
            archivo.chmod(0o600)
            ejecutar('keyvault', 'secret', 'set', '--vault-name', vault, '--name', nombre, '--file', str(archivo))
    # Procesos de fondo al final. No se crean bases ni se borran datos aquí.
    orden = ['keycloak', 'servicio-gestion', 'servicio-inventario', 'servicio-operaciones', 'servicio-ia', 'graphql-server', 'api-gateway', 'n8n', 'operaciones-consumidor', 'operaciones-programador']
    for nombre in orden:
        archivo = carpeta / (nombre + '.json')
        if not archivo.is_file():
            raise SystemExit('Falta manifiesto: ' + nombre)
        existe = subprocess.run(['az', 'containerapp', 'show', '--resource-group', args.grupo, '--name', 'sw2-' + nombre, '--only-show-errors', '--output', 'none'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if existe.returncode:
            # Distinguir inexistencia de otros errores para no ocultar fallos de acceso.
            if b'not found' not in existe.stderr.lower() and b'could not be found' not in existe.stderr.lower() and b'resourcenotfound' not in existe.stderr.lower():
                raise SystemExit('No se pudo consultar Container App ' + nombre + '; revisar permisos y grupo.')
            ejecutar('containerapp', 'create', '--resource-group', args.grupo, '--yaml', str(archivo))
        else:
            ejecutar('containerapp', 'update', '--resource-group', args.grupo, '--name', 'sw2-' + nombre, '--yaml', str(archivo))
        print('Aplicado: ' + nombre, flush=True)


if __name__ == '__main__':
    main()
