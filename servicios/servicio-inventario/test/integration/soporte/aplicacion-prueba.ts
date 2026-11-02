import 'reflect-metadata';
import { randomUUID } from 'node:crypto';
import { NestExpressApplication } from '@nestjs/platform-express';
import { Test, TestingModuleBuilder } from '@nestjs/testing';
import { createLocalJWKSet } from 'jose';
import { Connection } from 'mongoose';
import request from 'supertest';
import { App } from 'supertest/types';
import { Decimal } from '../../../src/domain/shared/decimal';
import { EvaluacionStockBajo } from '../../../src/adapters/inbound/evaluacion-stock-bajo';
import { CONJUNTO_CLAVES } from '../../../src/adapters/inbound/http/auth/jwt.guardia';
import { ESPERAS_REINTENTO_SAGA } from '../../../src/adapters/inbound/messaging/comandos-saga.consumidor';
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
      .useValue(createLocalJWKSet(tokens.jwks))
      // Reintentos de la Saga en milisegundos, para no esperar 7 s por test.
      .overrideProvider(ESPERAS_REINTENTO_SAGA)
      .useValue([10, 20, 40]),
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

/** Crea un insumo por la API como administrador y devuelve su id. */
export async function crearInsumoApi(
  ap: AplicacionPrueba,
  cambios: Record<string, unknown> = {},
): Promise<string> {
  const respuesta = await request(ap.servidor)
    .post(`${PREFIJO}/insumos`)
    .set('Authorization', await ap.tokens.bearer(['administrador']))
    .send(datosInsumo(cambios));
  if (respuesta.status !== 201) {
    throw new Error(`No se pudo crear el insumo: ${JSON.stringify(respuesta.body)}`);
  }
  return respuesta.body.id;
}

/** Stock guardado de un insumo, con escala 3. */
export async function stockDe(ap: AplicacionPrueba, idInsumo: string): Promise<string> {
  const insumo = await ap.conexion.collection('insumos').findOne({ _id: idInsumo as never });
  return new Decimal(String(insumo?.stock)).toFixed(3);
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
