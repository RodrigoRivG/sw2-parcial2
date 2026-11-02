import 'reflect-metadata';
import { randomUUID } from 'node:crypto';
import { NestExpressApplication } from '@nestjs/platform-express';
import { Test, TestingModuleBuilder } from '@nestjs/testing';
import { createLocalJWKSet } from 'jose';
import { Connection } from 'mongoose';
import { App } from 'supertest/types';
import { EvaluacionStockBajo } from '../../../src/adapters/inbound/evaluacion-stock-bajo';
import { CONJUNTO_CLAVES } from '../../../src/adapters/inbound/http/auth/jwt.guardia';
import { configurarAplicacion } from '../../../src/adapters/inbound/http/configurar-aplicacion';
import { CONEXION_MONGO } from '../../../src/adapters/outbound/persistence/conexion-mongo';
import { AppModule } from '../../../src/app.module';
import { CONFIGURACION, Configuracion } from '../../../src/config/validacion-entorno';
import { AUDIENCIA_PRUEBA, EMISOR_PRUEBA, FabricaTokens } from './fabrica-tokens';

export const PREFIJO = '/api/inventario/v1';

export interface AplicacionPrueba {
  app: NestExpressApplication;
  servidor: App;
  conexion: Connection;
  tokens: FabricaTokens;
  cerrar(): Promise<void>;
}

/**
 * Levanta la aplicación completa contra el MongoDB de Testcontainers, en una base de datos propia,
 * con la misma configuración HTTP que `main.ts`.
 */
export async function crearAplicacionPrueba(
  sobrescribir: (constructor: TestingModuleBuilder) => TestingModuleBuilder = (c) => c,
  cambiosConfiguracion: Partial<Configuracion> = {},
): Promise<AplicacionPrueba> {
  const base = process.env.MONGODB_PRUEBAS_URI;
  const rabbitmqUrl = process.env.RABBITMQ_PRUEBAS_URL;
  if (!base || !rabbitmqUrl) {
    throw new Error('Faltan MONGODB_PRUEBAS_URI o RABBITMQ_PRUEBAS_URL: falta el globalSetup de Jest.');
  }
  const configuracion: Configuracion = {
    puerto: 0,
    mongodbUri: `${base}/inventario_${randomUUID().slice(0, 8)}?directConnection=true`,
    rabbitmqUrl,
    keycloakIssuer: EMISOR_PRUEBA,
    keycloakJwksUri: 'http://keycloak-ficticio/realms/agro/protocol/openid-connect/certs',
    keycloakAudience: AUDIENCIA_PRUEBA,
    ...cambiosConfiguracion,
  };
  const tokens = await FabricaTokens.crear();
  const modulo = await sobrescribir(
    Test.createTestingModule({ imports: [AppModule] })
      .overrideProvider(CONFIGURACION)
      .useValue(configuracion)
      .overrideProvider(CONJUNTO_CLAVES)
      .useValue(createLocalJWKSet(tokens.jwks)),
  ).compile();

  const app = modulo.createNestApplication<NestExpressApplication>({
    bodyParser: false,
    logger: false,
  });
  configurarAplicacion(app);
  // Escucha en un puerto libre: supertest reutiliza el servidor en vez de abrir uno por solicitud.
  await app.listen(0);
  const conexion = app.get<Connection>(CONEXION_MONGO);

  return {
    app,
    servidor: app.getHttpServer(),
    conexion,
    tokens,
    async cerrar() {
      await app.get(EvaluacionStockBajo).esperarPendientes();
      if (conexion.readyState === 1) {
        await conexion.dropDatabase();
      }
      await app.close();
    },
  };
}

/** Reloj que el test mueve a mano (regla de 24 h). Reemplaza a `RelojSistema`. */
export class RelojPrueba {
  constructor(public instante = new Date('2026-11-02T10:00:00Z')) {}

  ahora(): Date {
    return new Date(this.instante);
  }

  avanzar(milisegundos: number): void {
    this.instante = new Date(this.instante.getTime() + milisegundos);
  }
}

/** Cuerpo válido para crear un insumo, con los campos que se quieran cambiar. */
export function datosInsumo(cambios: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    nombre: 'Urea 46 %',
    categoria: 'FERTILIZANTE',
    unidad: 'KILOGRAMO',
    nivelMinimo: '50',
    costoUnitario: '4.85',
    descripcion: 'Bolsa de 50 kg',
    ...cambios,
  };
}
