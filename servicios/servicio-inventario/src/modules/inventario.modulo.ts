import { Module } from '@nestjs/common';
import { APP_GUARD } from '@nestjs/core';
import { createRemoteJWKSet } from 'jose';
import { Connection } from 'mongoose';
import { CONJUNTO_CLAVES, JwtGuardia } from '../adapters/inbound/http/auth/jwt.guardia';
import { RolesGuardia } from '../adapters/inbound/http/auth/roles.guardia';
import { InsumosControlador } from '../adapters/inbound/http/insumos.controlador';
import { SaludControlador } from '../adapters/inbound/http/salud.controlador';
import {
  CONEXION_MONGO,
  CierreConexionMongo,
  crearConexionMongo,
} from '../adapters/outbound/persistence/conexion-mongo';
import { RegistroAuditoriaMongo } from '../adapters/outbound/persistence/registro-auditoria.mongo';
import { RepositorioInsumoMongo } from '../adapters/outbound/persistence/repositorio-insumo.mongo';
import { esquemaInsumo } from '../adapters/outbound/persistence/schemas/insumo.esquema';
import { esquemaRegistroAuditoria } from '../adapters/outbound/persistence/schemas/registro-auditoria.esquema';
import { UnidadTrabajoMongo } from '../adapters/outbound/persistence/unidad-trabajo.mongo';
import { RelojSistema } from '../adapters/outbound/reloj-sistema';
import { ActualizarInsumoCasoUso } from '../application/use-cases/actualizar-insumo.caso-uso';
import { ConsultarInsumosCasoUso } from '../application/use-cases/consultar-insumos.caso-uso';
import { CrearInsumoCasoUso } from '../application/use-cases/crear-insumo.caso-uso';
import { CONFIGURACION, Configuracion, leerConfiguracion } from '../config/validacion-entorno';

/** Conecta los puertos de `application` con los adaptadores. Los casos de uso no conocen Nest. */
@Module({
  controllers: [InsumosControlador, SaludControlador],
  providers: [
    { provide: CONFIGURACION, useFactory: () => leerConfiguracion() },
    {
      provide: CONEXION_MONGO,
      useFactory: (configuracion: Configuracion) => crearConexionMongo(configuracion.mongodbUri),
      inject: [CONFIGURACION],
    },
    CierreConexionMongo,
    {
      provide: CONJUNTO_CLAVES,
      useFactory: (configuracion: Configuracion) =>
        createRemoteJWKSet(new URL(configuracion.keycloakJwksUri)),
      inject: [CONFIGURACION],
    },
    { provide: APP_GUARD, useClass: JwtGuardia },
    { provide: APP_GUARD, useClass: RolesGuardia },
    { provide: RelojSistema, useValue: new RelojSistema() },
    {
      provide: UnidadTrabajoMongo,
      useFactory: (conexion: Connection) => new UnidadTrabajoMongo(conexion),
      inject: [CONEXION_MONGO],
    },
    {
      provide: RegistroAuditoriaMongo,
      useFactory: (conexion: Connection, reloj: RelojSistema) =>
        new RegistroAuditoriaMongo(
          conexion.model('RegistroAuditoria', esquemaRegistroAuditoria),
          reloj,
        ),
      inject: [CONEXION_MONGO, RelojSistema],
    },
    {
      provide: RepositorioInsumoMongo,
      useFactory: (conexion: Connection) =>
        new RepositorioInsumoMongo(conexion.model('Insumo', esquemaInsumo)),
      inject: [CONEXION_MONGO],
    },
    {
      provide: CrearInsumoCasoUso,
      useFactory: (
        repositorio: RepositorioInsumoMongo,
        unidadTrabajo: UnidadTrabajoMongo,
        auditoria: RegistroAuditoriaMongo,
        reloj: RelojSistema,
      ) => new CrearInsumoCasoUso(repositorio, unidadTrabajo, auditoria, reloj),
      inject: [RepositorioInsumoMongo, UnidadTrabajoMongo, RegistroAuditoriaMongo, RelojSistema],
    },
    {
      provide: ActualizarInsumoCasoUso,
      useFactory: (
        repositorio: RepositorioInsumoMongo,
        unidadTrabajo: UnidadTrabajoMongo,
        auditoria: RegistroAuditoriaMongo,
        reloj: RelojSistema,
      ) => new ActualizarInsumoCasoUso(repositorio, unidadTrabajo, auditoria, reloj),
      inject: [RepositorioInsumoMongo, UnidadTrabajoMongo, RegistroAuditoriaMongo, RelojSistema],
    },
    {
      provide: ConsultarInsumosCasoUso,
      useFactory: (repositorio: RepositorioInsumoMongo) =>
        new ConsultarInsumosCasoUso(repositorio),
      inject: [RepositorioInsumoMongo],
    },
  ],
})
export class InventarioModulo {}
