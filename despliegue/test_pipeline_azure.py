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
        (raiz / '.env.despliegue.compartidos').write_text('AZURE_KEYVAULT_URL=https://prueba.vault.azure.net\n')
        (raiz / '.env.despliegue.azure').write_text('NUBE=azure\n')
        carpeta = raiz / 'despliegue/generado/listo/azure'
        carpeta.mkdir(parents=True)
        (carpeta / 'secretos.json').write_text(json.dumps({'sw2-prueba': valor}))
        nombres = ['keycloak', 'servicio-gestion', 'servicio-inventario', 'servicio-operaciones', 'servicio-ia', 'graphql-server', 'api-gateway', 'n8n', 'operaciones-consumidor', 'operaciones-programador']
        for nombre in nombres:
            (carpeta / (nombre + '.json')).write_text('{}')
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
                return subprocess.CompletedProcess(args, 0, stderr=b'')

            with patch.object(a, 'RAIZ', raiz), patch.object(a.subprocess, 'run', side_effect=ejecutar), patch.object(sys, 'argv', ['aplicar', '--grupo', 'grupo-prueba']):
                a.main()
        actualizaciones = [c[c.index('--name') + 1] for c in llamadas if c[:3] == ['az', 'containerapp', 'update']]
        self.assertEqual(actualizaciones, ['sw2-' + n for n in nombres])

    def test_catalogo_incompleto_no_ejecuta_azure(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            self.escenario(raiz, '')
            with patch.object(a, 'RAIZ', raiz), patch.object(a.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as ejecutar, patch.object(sys, 'argv', ['aplicar', '--grupo', 'grupo-prueba']):
                with self.assertRaises(SystemExit):
                    a.main()
                self.assertFalse(any(c.args[0][0] == 'az' for c in ejecutar.call_args_list))


if __name__ == '__main__': unittest.main()
