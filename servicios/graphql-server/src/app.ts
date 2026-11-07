import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ApolloServer, type ApolloServerPlugin } from '@apollo/server';
import { ApolloServerPluginLandingPageDisabled } from '@apollo/server/plugin/disabled';
import { ApolloServerPluginLandingPageLocalDefault } from '@apollo/server/plugin/landingPage/default';
import { expressMiddleware } from '@as-integrations/express5';
import express, { type ErrorRequestHandler, type Express } from 'express';
import type { Configuracion } from './config';
import { crearContexto, type Contexto } from './contexto';
import { crearResolvers } from './esquema/resolvers';
import { soloConsultas } from './esquema/solo-consultas';
import { ClienteGateway } from './fuentes/cliente-gateway';
import { TokenServicio } from './fuentes/token-servicio';
import { autenticacion } from './seguridad/autenticacion';
import { crearValidadorToken, type ValidadorToken } from './seguridad/validar-token';
import { corsDesarrollo } from './web/cors-desarrollo';
import { correlacion, RUTA_GRAPHQL } from './web/correlacion';
import { formatearError, responderError } from './web/errores';
import { logger } from './web/logger';
import { registroAcceso } from './web/registro-acceso';

export interface Aplicacion {
  app: Express;
  detener: () => Promise<void>;
}

/** Agrega el idCorrelacion a cada error y deja la operación y la cantidad de errores para el log de acceso. */
const pluginEstadisticas: ApolloServerPlugin<Contexto> = {
  async requestDidStart() {
    return {
      async willSendResponse({ response, contextValue, operationName }) {
        const errores = response.body.kind === 'single' ? (response.body.singleResult.errors ?? []) : [];
        for (const error of errores) {
          (error as { extensions?: Record<string, unknown> }).extensions = {
            ...error.extensions,
            idCorrelacion: contextValue.idCorrelacion,
          };
        }
        contextValue.estadisticas.operacion = operationName ?? 'anonima';
        contextValue.estadisticas.errores = errores.length;
      },
    };
  },
};

export async function crearAplicacion(
  configuracion: Configuracion,
  validar: ValidadorToken = crearValidadorToken(configuracion),
): Promise<Aplicacion> {
  const servidor = new ApolloServer<Contexto>({
    typeDefs: readFileSync(join(__dirname, 'esquema', 'esquema.graphql'), 'utf8'),
    resolvers: crearResolvers(),
    introspection: true,
    includeStacktraceInErrorResponses: false,
    validationRules: [soloConsultas],
    formatError: formatearError,
    plugins: [
      pluginEstadisticas,
      configuracion.produccion
        ? ApolloServerPluginLandingPageDisabled()
        : ApolloServerPluginLandingPageLocalDefault({ embed: true }),
    ],
  });
  await servidor.start();

  const cliente = new ClienteGateway(configuracion, new TokenServicio(configuracion));
  const app = express();
  app.disable('x-powered-by');
  // Orden de 2.5: correlación (con el plazo) → registro de acceso → CORS de desarrollo → salud → autenticación → Apollo.
  app.use(correlacion(configuracion.plazoConsultaMs));
  app.use(registroAcceso);
  app.use(corsDesarrollo(configuracion.produccion));
  app.get(['/salud', '/salud/liveness', '/salud/readiness'], (_req, res) => {
    res.json({ estado: 'UP' });
  });
  app.use(
    RUTA_GRAPHQL,
    autenticacion(validar, configuracion.produccion),
    express.json(),
    expressMiddleware(servidor, {
      context: async ({ res }) => crearContexto(cliente, res.locals),
    }),
  );
  const manejarError: ErrorRequestHandler = (error, _req, res, _next) => {
    const estado = (error as { status?: number }).status ?? 500;
    if (estado >= 500) {
      logger.error('Error inesperado', { idCorrelacion: res.locals.idCorrelacion, error: String(error) });
    }
    responderError(res, estado < 500 ? 'DATOS_INVALIDOS' : 'ERROR_INTERNO');
  };
  app.use(manejarError);

  return { app, detener: () => servidor.stop() };
}
