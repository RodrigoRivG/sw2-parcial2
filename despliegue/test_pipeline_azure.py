"""Comprueba la orquestación sin ejecutar Azure CLI ni construir imágenes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('aplicar', Path(__file__).resolve().parents[1] / 'scripts/aplicar-azure.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class PipelineAzure(unittest.TestCase):
    def escenario(self, raiz, valor):
        (raiz / '.env.despliegue.compartidos').write_text('AZURE_KEYVAULT_URL=https://prueba.vault.azure.net\nAZURE_ENVIRONMENT_ID=/subscriptions/prueba/resourceGroups/grupo-prueba/providers/Microsoft.App/managedEnvironments/entorno\nAZURE_ENVIRONMENT_DOMAIN=prueba.azurecontainerapps.io\n')
        (raiz / '.env.despliegue.azure').write_text('NUBE=azure\n')
        carpeta = raiz / 'despliegue/generado/listo/azure'
        carpeta.mkdir(parents=True)
        (carpeta / 'secretos.json').write_text(json.dumps({'sw2-prueba': valor}))
        nombres = ['keycloak', 'servicio-gestion', 'servicio-inventario', 'servicio-operaciones', 'servicio-ia', 'graphql-server', 'api-gateway', 'n8n', 'operaciones-consumidor', 'operaciones-programador']
        for nombre in nombres:
            (carpeta / (nombre + '.json')).write_text(json.dumps({'name': 'sw2-' + nombre, 'properties': {'environmentId': '/subscriptions/prueba/resourceGroups/grupo-prueba/providers/Microsoft.App/managedEnvironments/entorno'}}))
        return nombres

    def test_secretos_por_archivo_y_actualizacion_ordenada(self):
        llamadas = []
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            nombres = self.escenario(raiz, 'secreto-ficticio-no-publicar')

            def ejecutar(args, **kwargs):
                llamadas.append(args)
                self.assertNotIn('secreto-ficticio-no-publicar', ' '.join(args))
                if args[:4] == ['az', 'keyvault', 'secret', 'set']:
                    archivo = Path(args[args.index('--file') + 1])
                    self.assertEqual(archivo.read_text(), 'secreto-ficticio-no-publicar')
                    self.assertEqual(archivo.stat().st_mode & 0o777, 0o600)
                if args[:4] == ['az', 'containerapp', 'env', 'show']:
                    return subprocess.CompletedProcess(args, 0, stdout=json.dumps({'properties': {'provisioningState': 'Succeeded', 'defaultDomain': 'prueba.azurecontainerapps.io', 'environmentMode': 'WorkloadProfiles'}}), stderr='')
                if args[:3] == ['az', 'containerapp', 'show'] and args[args.index('--name') + 1] == 'sw2-keycloak':
                    return subprocess.CompletedProcess(args, 1, stderr=b'ResourceNotFound')
                return subprocess.CompletedProcess(args, 0, stdout=json.dumps({'properties': {'environmentId': '/subscriptions/prueba/resourceGroups/grupo-prueba/providers/Microsoft.App/managedEnvironments/entorno'}}).encode(), stderr=b'')

            with patch.object(a, 'RAIZ', raiz), patch.object(a.subprocess, 'run', side_effect=ejecutar), patch.object(sys, 'argv', ['aplicar', '--grupo', 'grupo-prueba']):
                a.main()
        actualizaciones = [c[c.index('--name') + 1] for c in llamadas if c[:3] == ['az', 'containerapp', 'update']]
        self.assertEqual(actualizaciones, ['sw2-' + n for n in nombres[1:]])
        creaciones = [c for c in llamadas if c[:3] == ['az', 'containerapp', 'create']]
        self.assertEqual(len(creaciones), 1)
        self.assertEqual(creaciones[0][creaciones[0].index('--name') + 1], 'sw2-keycloak')
        self.assertIn('--yaml', creaciones[0])
        self.assertEqual(creaciones[0][creaciones[0].index('--environment') + 1], '/subscriptions/prueba/resourceGroups/grupo-prueba/providers/Microsoft.App/managedEnvironments/entorno')

    def test_catalogo_incompleto_no_ejecuta_azure(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            self.escenario(raiz, '')
            with patch.object(a, 'RAIZ', raiz), patch.object(a.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as ejecutar, patch.object(sys, 'argv', ['aplicar', '--grupo', 'grupo-prueba']):
                with self.assertRaises(SystemExit):
                    a.main()
                self.assertFalse(any(c.args[0][0] == 'az' for c in ejecutar.call_args_list))

    def test_entorno_express_se_rechaza_antes_de_escribir(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            self.escenario(raiz, 'ficticio')
            v = a.leer(raiz / '.env.despliegue.compartidos')
            with patch.object(a, 'consultar', return_value={'properties': {'environmentMode': 'Express'}}), patch.object(a.subprocess, 'run') as ejecutar:
                with self.assertRaisesRegex(SystemExit, 'Express'):
                    a.comprobar(v, raiz / 'despliegue/generado/listo/azure', 'grupo-prueba')
                ejecutar.assert_not_called()

    def test_manifiesto_antiguo_falla_antes_de_consultar_azure(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            self.escenario(raiz, 'ficticio')
            v = a.leer(raiz / '.env.despliegue.compartidos')
            destino = raiz / 'despliegue/generado/listo/azure'
            (destino / 'keycloak.json').write_text(json.dumps({'name': 'sw2-keycloak', 'properties': {'managedEnvironmentId': v['AZURE_ENVIRONMENT_ID']}}))
            with patch.object(a, 'consultar') as consultar:
                with self.assertRaisesRegex(SystemExit, 'Regenerar'):
                    a.comprobar(v, destino, 'grupo-prueba')
                consultar.assert_not_called()

    def test_app_en_otro_entorno_no_se_modifica(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            self.escenario(raiz, 'ficticio')
            v = a.leer(raiz / '.env.despliegue.compartidos')
            with patch.object(a, 'consultar', return_value={'properties': {'provisioningState': 'Succeeded', 'defaultDomain': v['AZURE_ENVIRONMENT_DOMAIN']}}), patch.object(a.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout=b'{"properties":{"environmentId":"/otro/entorno"}}', stderr=b'')) as ejecutar:
                with self.assertRaisesRegex(SystemExit, 'otro entorno'):
                    a.comprobar(v, raiz / 'despliegue/generado/listo/azure', 'grupo-prueba')
                self.assertTrue(all(c.args[0][1:3] == ['containerapp', 'show'] for c in ejecutar.call_args_list))

    def test_solo_comprobar_no_carga_secretos_ni_crea_apps(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            self.escenario(raiz, 'ficticio')
            with patch.object(a, 'RAIZ', raiz), patch.object(a, 'comprobar', return_value={}) as comprobar, patch.object(a.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as ejecutar, patch.object(sys, 'argv', ['aplicar', '--grupo', 'grupo-prueba', '--solo-comprobar']):
                a.main()
                comprobar.assert_called_once()
                self.assertFalse(any(c.args[0][0] == 'az' for c in ejecutar.call_args_list))


if __name__ == '__main__': unittest.main()
