import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { NestExpressApplication } from '@nestjs/platform-express';
import { configurarAplicacion } from './adapters/inbound/http/configurar-aplicacion';
import { AppModule } from './app.module';
import { LoggerJson } from './config/logger-json';
import { CONFIGURACION, Configuracion } from './config/validacion-entorno';

async function iniciar(): Promise<void> {
  const app = await NestFactory.create<NestExpressApplication>(AppModule, {
    bodyParser: false,
    logger: new LoggerJson(),
  });
  configurarAplicacion(app);
  app.enableShutdownHooks();
  await app.listen(app.get<Configuracion>(CONFIGURACION).puerto);
}

void iniciar();
