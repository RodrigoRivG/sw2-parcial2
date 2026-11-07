import { crearAplicacion } from './app';
import { leerConfiguracion } from './config';
import { logger } from './web/logger';

async function arrancar(): Promise<void> {
  const configuracion = leerConfiguracion();
  const { app } = await crearAplicacion(configuracion);
  app.listen(configuracion.puerto, () => {
    logger.info('graphql-server escuchando', { puerto: configuracion.puerto });
  });
}

arrancar().catch((error: unknown) => {
  logger.error('No se pudo arrancar graphql-server', { error: String(error) });
  process.exit(1);
});
