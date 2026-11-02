import { GenericContainer, StartedTestContainer, Wait } from 'testcontainers';

declare global {
  var contenedorMongoPruebas: StartedTestContainer | undefined;
  var contenedorRabbitmqPruebas: StartedTestContainer | undefined;
}

const PUERTO_MONGO = 27017;
const PUERTO_RABBITMQ = 5672;
const ESPERA_PRIMARIO_MS = 60_000;
const USUARIO_RABBITMQ = 'prueba';

/**
 * Un solo MongoDB (replica set de un nodo) y un solo RabbitMQ, con las imágenes de Docker Compose,
 * para toda la corrida. Los workers de Jest heredan las variables; cada archivo usa su propia base.
 */
export default async function inicioGlobal(): Promise<void> {
  const [mongo, rabbitmq] = await Promise.allSettled([iniciarMongo(), iniciarRabbitmq()]);
  if (mongo.status === 'rejected' || rabbitmq.status === 'rejected') {
    await Promise.allSettled([
      globalThis.contenedorMongoPruebas?.stop(),
      globalThis.contenedorRabbitmqPruebas?.stop(),
    ]);
    throw [mongo, rabbitmq].find((r) => r.status === 'rejected')?.reason;
  }
}

/**
 * El replica set se inicia paso a paso, en lugar de usar el health check de `@testcontainers/mongodb`.
 * Si `mongod` termina al arrancar, el error muestra su log (así se diagnosticó SERVER-121912 en CI).
 */
async function iniciarMongo(): Promise<void> {
  const log: string[] = [];
  let contenedor: StartedTestContainer;
  try {
    contenedor = await new GenericContainer('mongo:8.0')
      .withCommand(['--replSet', 'rs0', '--bind_ip_all'])
      .withExposedPorts(PUERTO_MONGO)
      .withLogConsumer((flujo) => flujo.on('data', (linea) => log.push(String(linea))))
      .withWaitStrategy(Wait.forLogMessage(/Waiting for connections/))
      .withStartupTimeout(120_000)
      .start();
  } catch (error) {
    throw new Error(`MongoDB no arrancó: ${String(error)}\n${ultimasLineas('mongod', log)}`);
  }
  globalThis.contenedorMongoPruebas = contenedor;
  try {
    await iniciarReplicaSet(contenedor);
  } catch (error) {
    throw new Error(`${String(error)}\n${ultimasLineas('mongod', log)}`);
  }
  process.env.MONGODB_PRUEBAS_URI = `mongodb://${contenedor.getHost()}:${contenedor.getMappedPort(PUERTO_MONGO)}`;
}

/** Usuario propio: `guest` solo puede conectarse desde localhost dentro del contenedor. */
async function iniciarRabbitmq(): Promise<void> {
  const log: string[] = [];
  let contenedor: StartedTestContainer;
  try {
    contenedor = await new GenericContainer('rabbitmq:4-management-alpine')
      .withEnvironment({
        RABBITMQ_DEFAULT_USER: USUARIO_RABBITMQ,
        RABBITMQ_DEFAULT_PASS: USUARIO_RABBITMQ,
      })
      .withExposedPorts(PUERTO_RABBITMQ)
      .withLogConsumer((flujo) => flujo.on('data', (linea) => log.push(String(linea))))
      .withWaitStrategy(Wait.forLogMessage(/Server startup complete/))
      .withStartupTimeout(120_000)
      .start();
  } catch (error) {
    throw new Error(`RabbitMQ no arrancó: ${String(error)}\n${ultimasLineas('rabbitmq', log)}`);
  }
  globalThis.contenedorRabbitmqPruebas = contenedor;
  process.env.RABBITMQ_PRUEBAS_URL = `amqp://${USUARIO_RABBITMQ}:${USUARIO_RABBITMQ}@${contenedor.getHost()}:${contenedor.getMappedPort(PUERTO_RABBITMQ)}`;
}

async function iniciarReplicaSet(contenedor: StartedTestContainer): Promise<void> {
  const inicio = await mongosh(
    contenedor,
    `rs.initiate({ _id: 'rs0', members: [{ _id: 0, host: 'localhost:${PUERTO_MONGO}' }] }).ok`,
  );
  if (inicio.exitCode !== 0 || inicio.output.trim() !== '1') {
    throw new Error(`No se pudo iniciar el replica set de MongoDB: ${inicio.output}`);
  }
  const limite = Date.now() + ESPERA_PRIMARIO_MS;
  let ultimo = '';
  while (Date.now() < limite) {
    const estado = await mongosh(contenedor, 'db.hello().isWritablePrimary');
    ultimo = estado.output.trim();
    if (estado.exitCode === 0 && ultimo === 'true') {
      return;
    }
    await new Promise((resolver) => setTimeout(resolver, 250));
  }
  throw new Error(`MongoDB no llegó a ser PRIMARY en ${ESPERA_PRIMARIO_MS} ms: ${ultimo}`);
}

function ultimasLineas(proceso: string, log: string[]): string {
  const lineas = log.join('').split('\n').filter(Boolean);
  return `Últimas líneas del log de ${proceso}:\n${lineas.slice(-40).join('\n')}`;
}

function mongosh(contenedor: StartedTestContainer, comando: string) {
  return contenedor.exec(['mongosh', '--quiet', '--eval', comando]);
}
