import { MongoDBContainer, StartedMongoDBContainer } from '@testcontainers/mongodb';

declare global {
  var contenedorMongoPruebas: StartedMongoDBContainer | undefined;
}

/** Un solo MongoDB (replica set de un nodo, la misma imagen de Docker Compose) para toda la corrida. */
export default async function inicioGlobal(): Promise<void> {
  const contenedor = await new MongoDBContainer('mongo:8.0').start();
  globalThis.contenedorMongoPruebas = contenedor;
  // Los workers de Jest heredan esta variable; cada archivo usa su propia base de datos.
  process.env.MONGODB_PRUEBAS_URI = contenedor.getConnectionString();
}
