import { GenericContainer, StartedTestContainer, Wait } from 'testcontainers';

declare global {
  var contenedorMongoPruebas: StartedTestContainer | undefined;
}

const PUERTO_MONGO = 27017;
const ESPERA_PRIMARIO_MS = 60_000;

/**
 * Un solo MongoDB (replica set de un nodo, la misma imagen de Docker Compose) para toda la corrida.
 * El replica set se inicia aquí, paso a paso, en lugar de usar el health check de
 * `@testcontainers/mongodb`, que en GitHub Actions terminaba `unhealthy` sin más detalle.
 */
export default async function inicioGlobal(): Promise<void> {
  const contenedor = await new GenericContainer('mongo:8.0')
    .withCommand(['--replSet', 'rs0', '--bind_ip_all'])
    .withExposedPorts(PUERTO_MONGO)
    .withWaitStrategy(Wait.forLogMessage(/Waiting for connections/))
    .withStartupTimeout(120_000)
    .start();
  globalThis.contenedorMongoPruebas = contenedor;
  try {
    await iniciarReplicaSet(contenedor);
  } catch (error) {
    await contenedor.stop();
    throw error;
  }
  // Los workers de Jest heredan esta variable; cada archivo usa su propia base de datos.
  process.env.MONGODB_PRUEBAS_URI = `mongodb://${contenedor.getHost()}:${contenedor.getMappedPort(PUERTO_MONGO)}`;
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

function mongosh(contenedor: StartedTestContainer, comando: string) {
  return contenedor.exec(['mongosh', '--quiet', '--eval', comando]);
}
