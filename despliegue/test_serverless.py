"""Contratos de ejecución nativa, con datos ficticios y sin acceso cloud."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from configuracion import Secreto, completar_urls, servicios

spec = importlib.util.spec_from_file_location('generador', Path(__file__).resolve().parents[1] / 'scripts/generar-serverless.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class Manifiestos(unittest.TestCase):
    def setUp(self):
        self.v = {'IMAGEN_PREFIJO': 'registro.ficticio/sw2', 'IMAGEN_ETIQUETA': 'prueba', 'API_GATEWAY_URL': 'https://gateway.ficticio', 'KEYCLOAK_ISSUER': 'https://auth.ficticio/realms/agro', 'GCP_SERVICE_ACCOUNT_EMAIL': 'app@ficticio.iam.gserviceaccount.com', 'N8N_PUBLIC_URL': 'https://n8n.ficticio', 'AZURE_IDENTITY_ID': '/identidad/ficticia', 'AZURE_KEYVAULT_URL': 'https://ficticio.vault.azure.net', 'AWS_ACCOUNT_ID': '123456789012', 'AWS_ACCESS_KEY_ID': 'CLAVE_FICTICIA', 'AWS_SECRET_ACCESS_KEY': 'SECRETO_FICTICIO', 'IA_CLIENT_SECRET': 'SECRETO_IA_FICTICIO', 'GCP_IA_CREDENCIALES_ARCHIVO': '/no-existe-ficticio.json'}

    def test_azure_autonomo_y_gateway_de_su_nube(self):
        for nube in ['aws', 'azure', 'gcp']:
            v = {**self.v, 'API_GATEWAY_URL': 'https://gateway.' + nube, 'GESTION_URL': 'https://gestion.' + nube}
            s = servicios(nube, v, self.v)
            esperado = 'true' if nube == 'azure' else 'false'
            self.assertEqual(s['servicio-inventario']['env']['RABBITMQ_CONSUMIDOR_ACTIVO'], esperado)
            self.assertEqual(s['servicio-gestion']['env']['SPRING_RABBITMQ_LISTENER_SIMPLE_AUTO_STARTUP'], esperado)
            self.assertEqual(s['servicio-ia']['env']['TRABAJOS_CONSUMIDOR_ACTIVO'], esperado)
            self.assertEqual(s['api-gateway']['env']['GESTION_URL'], 'https://gestion.' + nube)
            self.assertEqual(s['graphql-server']['env']['API_GATEWAY_URL'], 'https://gateway.' + nube)
            self.assertNotIn('ollama', s)
            if nube == 'azure':
                self.assertEqual(s['operaciones-programador']['env']['API_GATEWAY_URL'], 'https://gateway.azure')
                self.assertEqual(s['n8n']['env']['API_GATEWAY_URL'], 'https://gateway.azure')

    def test_cloud_run_cpu_y_postgres_n8n(self):
        s = servicios('gcp', {**self.v, 'CONSUMIDORES_ACTIVOS': 'true', 'N8N_NUBE': 'gcp'}, self.v)
        self.assertEqual(len(s), 8)
        for n in ['servicio-gestion', 'servicio-inventario', 'servicio-ia', 'keycloak', 'n8n']:
            m = g.cloud_run(n, s[n], self.v)
            self.assertEqual(m['metadata']['annotations']['run.googleapis.com/minScale'], '1')
            self.assertEqual(m['metadata']['annotations']['run.googleapis.com/maxScale'], '1')
            self.assertEqual(m['spec']['template']['metadata']['annotations']['run.googleapis.com/cpu-throttling'], 'false')
        self.assertEqual(s['n8n']['env']['DB_TYPE'], 'postgresdb')
        self.assertIsInstance(s['keycloak']['env']['IA_CLIENT_SECRET'], Secreto)
        self.assertNotIn('GOOGLE_CREDENTIALS_JSON', s['servicio-ia']['env'])
        n8n = g.cloud_run('n8n', s['n8n'], self.v)
        self.assertEqual(n8n['spec']['template']['spec']['volumes'][0]['secret']['secretName'], 'sw2-firebase-json')

    def test_azure_procesos_sin_ingress_y_secret_refs(self):
        s = servicios('azure', self.v, self.v)
        self.assertEqual(len(s), 10)
        for n in ['operaciones-programador', 'operaciones-consumidor']:
            m = g.container_app(n, s[n], self.v)
            self.assertNotIn('ingress', m['properties']['configuration'])
            self.assertEqual(m['properties']['template']['scale'], {'minReplicas': 1, 'maxReplicas': 1})
            self.assertEqual(m['properties']['configuration']['activeRevisionsMode'], 'Single')
        m = g.container_app('servicio-ia', s['servicio-ia'], self.v)
        self.assertNotIn('SECRETO_IA_FICTICIO', json.dumps(m))
        self.assertTrue(m['properties']['configuration']['secrets'])
        for nombre in ['keycloak', 'n8n']:
            m = g.container_app(nombre, s[nombre], self.v)
            self.assertIn('tcpSocket', m['properties']['template']['containers'][0]['probes'][1])
        m = g.container_app('n8n', s['n8n'], self.v)
        self.assertEqual(m['properties']['template']['volumes'][0]['storageType'], 'Secret')

    def test_app_runner_port_reservado_y_ssm_sin_secretos_planos(self):
        s = servicios('aws', self.v, self.v)
        self.assertEqual(len(s), 7)
        m = g.app_runner('servicio-ia', s['servicio-ia'], self.v)
        c = m['SourceConfiguration']['ImageRepository']['ImageConfiguration']
        self.assertNotIn('PORT', c['RuntimeEnvironmentVariables'])
        self.assertEqual(c['Port'], '8080')
        self.assertIn('GOOGLE_CREDENTIALS_JSON', c['RuntimeEnvironmentSecrets'])
        self.assertNotIn('SECRETO_IA_FICTICIO', json.dumps(m))
        self.assertEqual(m['InstanceConfiguration']['Memory'], '2048')

    def test_urls_azure_deducidas_del_dominio_y_ia_sin_llm(self):
        dominio = 'feliz-123.brazilsouth.azurecontainerapps.io'
        v = completar_urls('azure', {'AZURE_ENVIRONMENT_DOMAIN': dominio, 'GESTION_URL': 'https://gestion-azure.example', 'IA_URL': 'https://ia.propia'})
        self.assertEqual(v['GESTION_URL'], 'https://sw2-servicio-gestion.' + dominio)
        self.assertEqual(v['API_GATEWAY_URL'], 'https://sw2-api-gateway.' + dominio)
        self.assertEqual(v['N8N_PUBLIC_URL'], 'https://sw2-n8n.' + dominio)
        self.assertEqual(v['IA_URL'], 'https://ia.propia')
        self.assertEqual(v['KEYCLOAK_TOKEN_URL'], f'https://sw2-keycloak.{dominio}/realms/agro/protocol/openid-connect/token')
        self.assertEqual(completar_urls('gcp', {'AZURE_ENVIRONMENT_DOMAIN': dominio}), {'AZURE_ENVIRONMENT_DOMAIN': dominio})
        s = servicios('azure', self.v, self.v)
        recursos = {n: g.container_app(n, s[n], self.v)['properties']['template']['containers'][0]['resources'] for n in ['servicio-ia', 'servicio-gestion', 'operaciones-programador']}
        self.assertEqual(recursos['servicio-ia'], {'cpu': 1.0, 'memory': '2.0Gi'})
        self.assertEqual(recursos['servicio-gestion'], {'cpu': 0.5, 'memory': '1.0Gi'})
        self.assertEqual(recursos['operaciones-programador'], {'cpu': 0.25, 'memory': '0.5Gi'})


if __name__ == '__main__': unittest.main()
