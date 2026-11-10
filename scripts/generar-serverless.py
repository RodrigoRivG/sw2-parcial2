#!/usr/bin/env python3
"""Genera manifiestos nativos; no crea recursos ni imprime secretos."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'despliegue'))
from configuracion import RAIZ, Secreto, completar_urls, leer, servicios


def guardar(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as salida:
        json.dump(datos, salida, ensure_ascii=False, indent=2)
        salida.write('\n')


def nombre_secreto(nombre):
    return 'sw2-' + nombre


def cloud_run(nombre, s, v):
    env = []
    for k, x in s['env'].items():
        if k == 'PORT': continue  # Cloud Run lo inyecta a partir de containerPort.
        env.append({'name': k, 'valueFrom': {'secretKeyRef': {'name': nombre_secreto(x.nombre), 'key': 'latest'}}} if isinstance(x, Secreto) else {'name': k, 'value': x})
    c = {'image': s['imagen'], 'ports': [{'containerPort': s['puerto']}], 'env': env,
         'resources': {'limits': {'cpu': str(s['cpu']), 'memory': str(s['memoria']) + 'Mi'}},
         'startupProbe': {'tcpSocket': {'port': s['puerto']}, 'periodSeconds': 10, 'failureThreshold': 24, 'timeoutSeconds': 2}}
    spec = {'serviceAccountName': v.get('GCP_SERVICE_ACCOUNT_EMAIL', 'CUENTA_PENDIENTE'), 'containerConcurrency': 4 if nombre == 'servicio-ia' else 20, 'timeoutSeconds': 300, 'containers': [c]}
    if nombre == 'n8n':
        c['volumeMounts'] = [{'name': 'firebase', 'mountPath': '/run/secrets'}]
        spec['volumes'] = [{'name': 'firebase', 'secret': {'secretName': 'sw2-firebase-json', 'items': [{'key': 'latest', 'path': 'firebase.json'}]}}]
    return {'apiVersion': 'serving.knative.dev/v1', 'kind': 'Service', 'metadata': {'name': 'sw2-' + nombre, 'annotations': {'run.googleapis.com/ingress': 'all', 'run.googleapis.com/invoker-iam-disabled': 'true', 'run.googleapis.com/minScale': '1' if s['continuo'] else '0', 'run.googleapis.com/maxScale': '1'}}, 'spec': {'template': {'metadata': {'annotations': {'run.googleapis.com/cpu-throttling': 'false' if s['continuo'] else 'true', 'run.googleapis.com/startup-cpu-boost': 'true'}}, 'spec': spec}, 'traffic': [{'latestRevision': True, 'percent': 100}]}}


def container_app(nombre, s, v):
    identidad = v.get('AZURE_IDENTITY_ID', 'IDENTIDAD_PENDIENTE')
    secretos = {nombre_secreto(x.nombre): {'name': nombre_secreto(x.nombre), 'keyVaultUrl': v.get('AZURE_KEYVAULT_URL', 'https://VAULT_PENDIENTE.vault.azure.net').rstrip('/') + '/secrets/' + nombre_secreto(x.nombre), 'identity': identidad} for x in s['env'].values() if isinstance(x, Secreto)}
    config = {'activeRevisionsMode': 'Single', 'secrets': list(secretos.values()), 'registries': [{'server': s['imagen'].split('/')[0], 'identity': identidad}]}
    if s['puerto']:
        config['ingress'] = {'external': True, 'targetPort': s['puerto'], 'transport': 'auto', 'allowInsecure': False}
    # Container Apps exige pares fijos de CPU/memoria (0,5 vCPU por GiB).
    c = {'name': nombre, 'image': s['imagen'], 'resources': {'cpu': s['memoria'] / 2048, 'memory': str(s['memoria'] / 1024) + 'Gi'}, 'env': [{'name': k, **({'secretRef': nombre_secreto(x.nombre)} if isinstance(x, Secreto) else {'value': x})} for k, x in s['env'].items()]}
    if s.get('comando'): c['command'] = s['comando']
    if s['puerto']:
        c['probes'] = [{'type': 'Startup', 'tcpSocket': {'port': s['puerto']}, 'periodSeconds': 5, 'failureThreshold': 60}, {'type': 'Liveness', 'httpGet': {'path': '/salud/liveness', 'port': s['puerto']}, 'periodSeconds': 30, 'failureThreshold': 3}]
    if nombre in {'keycloak', 'n8n'}:
        c['probes'][1].pop('httpGet')
        c['probes'][1]['tcpSocket'] = {'port': s['puerto']}
    template = {'containers': [c], 'scale': {'minReplicas': 1 if s['continuo'] else 0, 'maxReplicas': 1}}
    if nombre == 'n8n':
        secreto = 'sw2-firebase-json'
        config['secrets'].append({'name': secreto, 'keyVaultUrl': v.get('AZURE_KEYVAULT_URL', '').rstrip('/') + '/secrets/' + secreto, 'identity': identidad})
        c['volumeMounts'] = [{'volumeName': 'firebase', 'mountPath': '/run/secrets'}]
        template['volumes'] = [{'name': 'firebase', 'storageType': 'Secret', 'secrets': [{'secretRef': secreto, 'path': 'firebase.json'}]}]
    return {'name': 'sw2-' + nombre, 'type': 'Microsoft.App/containerApps', 'location': v.get('AZURE_LOCATION', 'eastus'), 'identity': {'type': 'UserAssigned', 'userAssignedIdentities': {identidad: {}}}, 'properties': {'environmentId': v.get('AZURE_ENVIRONMENT_ID', 'ENTORNO_PENDIENTE'), 'configuration': config, 'template': template}}


def app_runner(nombre, s, v):
    arn_prefix = f"arn:aws:ssm:{v.get('AWS_DEFAULT_REGION', 'us-east-1')}:{v.get('AWS_ACCOUNT_ID', 'CUENTA_PENDIENTE')}:parameter/sw2/"
    config = {'Port': str(s['puerto']), 'RuntimeEnvironmentVariables': {k: x for k, x in s['env'].items() if not isinstance(x, Secreto) and k != 'PORT'}, 'RuntimeEnvironmentSecrets': {k: arn_prefix + nombre_secreto(x.nombre) for k, x in s['env'].items() if isinstance(x, Secreto)}}
    # App Runner asigna PORT a partir de ImageConfiguration.Port; no acepta PORT explícito.
    resultado = {'ServiceName': 'sw2-' + nombre, 'SourceConfiguration': {'ImageRepository': {'ImageIdentifier': s['imagen'], 'ImageRepositoryType': 'ECR', 'ImageConfiguration': config}, 'AutoDeploymentsEnabled': False, 'AuthenticationConfiguration': {'AccessRoleArn': v.get('AWS_APP_RUNNER_ECR_ROLE_ARN', 'ROL_ECR_PENDIENTE')}}, 'InstanceConfiguration': {'Cpu': str(s['cpu'] * 1024), 'Memory': str(s['memoria']), 'InstanceRoleArn': v.get('AWS_APP_RUNNER_INSTANCE_ROLE_ARN', 'ROL_INSTANCIA_PENDIENTE')}, 'HealthCheckConfiguration': {'Protocol': 'HTTP', 'Path': '/salud/liveness', 'Interval': 10, 'Timeout': 5, 'HealthyThreshold': 1, 'UnhealthyThreshold': 5}, 'AutoScalingConfigurationArn': v.get('AWS_APP_RUNNER_AUTOSCALING_ARN', 'ESCALADO_PENDIENTE'), 'NetworkConfiguration': {'EgressConfiguration': {'EgressType': 'DEFAULT'}}}

    if nombre == 'keycloak':
        resultado['HealthCheckConfiguration'] = {'Protocol': 'TCP', 'Interval': 10, 'Timeout': 5, 'HealthyThreshold': 1, 'UnhealthyThreshold': 5}
    return resultado


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('nube', choices=['aws', 'azure', 'gcp'])
    p.add_argument('--borrador', action='store_true', help='Permite valores pendientes; NO usar para desplegar')
    args = p.parse_args()
    if not args.borrador:
        r = subprocess.run([sys.executable, str(RAIZ / 'scripts/validar-despliegue.py'), args.nube])
        if r.returncode: raise SystemExit(r.returncode)
        if args.nube in {'gcp', 'azure'}:
            r = subprocess.run([sys.executable, str(RAIZ / 'scripts/validar-despliegue.py'), 'compartidos', '--nube', args.nube])
            if r.returncode: raise SystemExit(r.returncode)
    comunes = leer(RAIZ / '.env.despliegue.compartidos')
    valores = completar_urls(args.nube, {**leer(RAIZ / '.env.despliegue.example'), **comunes, **leer(RAIZ / f'.env.despliegue.{args.nube}')})
    salida = RAIZ / 'despliegue/generado' / ('borrador' if args.borrador else 'listo') / args.nube
    specs = servicios(args.nube, valores, comunes)
    catalogo = {}
    for nombre, s in specs.items():
        for x in s['env'].values():
            if isinstance(x, Secreto): catalogo[nombre_secreto(x.nombre)] = x.valor
        manifiesto = {'gcp': cloud_run, 'azure': container_app, 'aws': app_runner}[args.nube](nombre, s, valores)
        guardar(salida / (nombre + '.json'), manifiesto)
    if 'n8n' in specs:
        ruta = Path(valores.get('FIREBASE_CREDENCIALES_ARCHIVO', './secretos/firebase-cuenta-servicio.json'))
        if not ruta.is_absolute(): ruta = RAIZ / 'despliegue' / ruta
        catalogo['sw2-firebase-json'] = ruta.read_text() if ruta.is_file() else ''
    guardar(salida / 'secretos.json', catalogo)
    print(f'{len(specs)} manifiestos {args.nube} generados en {salida.relative_to(RAIZ)}; secretos en archivo privado (600).')
    if args.borrador: print('BORRADOR: completar configuración, validar y regenerar sin --borrador antes de desplegar.')


if __name__ == '__main__':
    main()
