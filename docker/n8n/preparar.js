// Prepara n8n antes de arrancar (spec-n8n.md 2.3 y 2.7):
// 1. Declara el exchange `eventos` (topic, durable), igual que los servicios, para que
//    el RabbitMQ Trigger pueda enlazar su cola aunque operaciones no haya arrancado.
// 2. Escribe en stdout el JSON de las dos credenciales, armado desde el entorno.
//    Si falta algo, sale con código 1 y no imprime nada.
const fs = require('fs');

const N8N = '/usr/local/lib/node_modules/n8n';
const env = process.env;

function falla(mensaje) {
  console.error(`[agro] ${mensaje}. No se importan credenciales ni flujos.`);
  process.exit(1);
}

const requeridas = ['RABBITMQ_HOST', 'RABBITMQ_USER', 'RABBITMQ_PASSWORD', 'FIREBASE_PROYECTO_ID', 'FIREBASE_CUENTA_SERVICIO'];
const faltantes = requeridas.filter((n) => !env[n]);
if (faltantes.length) falla(`Faltan variables: ${faltantes.join(', ')}`);

let cuenta;
try {
  cuenta = JSON.parse(fs.readFileSync(env.FIREBASE_CUENTA_SERVICIO, 'utf8'));
} catch (e) {
  falla(`No se pudo leer ${env.FIREBASE_CUENTA_SERVICIO} (T01)`);
}

const ssl = env.RABBITMQ_SSL === 'true';
const rabbit = {
  hostname: env.RABBITMQ_HOST,
  port: Number(env.RABBITMQ_PORT || (ssl ? 5671 : 5672)),
  username: env.RABBITMQ_USER,
  password: env.RABBITMQ_PASSWORD,
  vhost: env.RABBITMQ_VHOST || '/',
  ssl,
};

async function declararExchange() {
  const ruta = require.resolve('amqplib', { paths: [require.resolve('n8n-nodes-base/package.json', { paths: [N8N] })] });
  const amqp = require(ruta);
  const url = `${ssl ? 'amqps' : 'amqp'}://${encodeURIComponent(rabbit.username)}:${encodeURIComponent(rabbit.password)}@${rabbit.hostname}:${rabbit.port}/${encodeURIComponent(rabbit.vhost)}`;
  const conexion = await amqp.connect(url);
  const canal = await conexion.createChannel();
  await canal.assertExchange('eventos', 'topic', { durable: true });
  await conexion.close();
}

(async () => {
  try {
    await declararExchange();
  } catch (e) {
    falla(`No se pudo declarar el exchange eventos en RabbitMQ: ${e.message}`);
  }

  const credenciales = [
    { id: 'rabbitmqAgro', name: 'RabbitMQ agro', type: 'rabbitmq', data: rabbit },
    {
      id: 'firebaseFcm',
      name: 'Firebase FCM',
      type: 'googleApi',
      data: {
        email: cuenta.client_email,
        privateKey: cuenta.private_key,
        httpNode: true,
        scopes: 'https://www.googleapis.com/auth/firebase.messaging',
      },
    },
  ];
  process.stdout.write(JSON.stringify(credenciales));
})();
