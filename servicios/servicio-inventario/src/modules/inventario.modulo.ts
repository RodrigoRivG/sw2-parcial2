import { Module } from '@nestjs/common';
import { APP_GUARD } from '@nestjs/core';
import { AmqpConnectionManager } from 'amqp-connection-manager';
import { createRemoteJWKSet } from 'jose';
import { Connection } from 'mongoose';
import { CONJUNTO_CLAVES, JwtGuardia } from '../adapters/inbound/http/auth/jwt.guardia';
import { RolesGuardia } from '../adapters/inbound/http/auth/roles.guardia';
import { EstadoInventarioControlador } from '../adapters/inbound/http/estado-inventario.controlador';
import { InsumosControlador } from '../adapters/inbound/http/insumos.controlador';
import { MovimientosControlador } from '../adapters/inbound/http/movimientos.controlador';
import { SaludControlador } from '../adapters/inbound/http/salud.controlador';
import { EvaluacionStockBajo } from '../adapters/inbound/evaluacion-stock-bajo';
import {
  CONEXION_RABBITMQ,
  CierreConexionRabbitmq,
  crearConexionRabbitmq,
} from '../adapters/outbound/messaging/conexion-rabbitmq';
import { PublicadorEventosRabbitmq } from '../adapters/outbound/messaging/publicador-eventos.rabbitmq';
import {
  CONEXION_MONGO,
  CierreConexionMongo,
  crearConexionMongo,
} from '../adapters/outbound/persistence/conexion-mongo';
import { RegistroAuditoriaMongo } from '../adapters/outbound/persistence/registro-auditoria.mongo';
import { RepositorioInsumoMongo } from '../adapters/outbound/persistence/repositorio-insumo.mongo';
import { RepositorioMovimientoMongo } from '../adapters/outbound/persistence/repositorio-movimiento.mongo';
import { esquemaInsumo } from '../adapters/outbound/persistence/schemas/insumo.esquema';
import { esquemaMovimiento } from '../adapters/outbound/persistence/schemas/movimiento-inventario.esquema';
import { esquemaRegistroAuditoria } from '../adapters/outbound/persistence/schemas/registro-auditoria.esquema';
import { UnidadTrabajoMongo } from '../adapters/outbound/persistence/unidad-trabajo.mongo';
import { RelojSistema } from '../adapters/outbound/reloj-sistema';
import { ActualizarInsumoCasoUso } from '../application/use-cases/actualizar-insumo.caso-uso';
import { ConsultarEstadoInventarioCasoUso } from '../application/use-cases/consultar-estado-inventario.caso-uso';
import { ConsultarInsumosCasoUso } from '../application/use-cases/consultar-insumos.caso-uso';
import { ConsultarMovimientosCasoUso } from '../application/use-cases/consultar-movimientos.caso-uso';
import { CrearInsumoCasoUso } from '../application/use-cases/crear-insumo.caso-uso';
import { EvaluarStockBajoCasoUso } from '../application/use-cases/evaluar-stock-bajo.caso-uso';
import { RegistrarMovimientoCasoUso } from '../application/use-cases/registrar-movimiento.caso-uso';
import { CONFIGURACION, Configuracion, leerConfiguracion } from '../config/validacion-entorno';

/** Conecta los puertos de `application` con los adaptadores. Los casos de uso no conocen Nest. */
@Module({
  controllers: [
    InsumosControlador,
    MovimientosControlador,
    EstadoInventarioControlador,
    SaludControlador,
  ],
  providers: [
    { provide: CONFIGURACION, useFactory: () => leerConfiguracion() },
    {
      provide: CONEXION_MONGO,
      useFactory: (configuracion: Configuracion) => crearConexionMongo(configuracion.mongodbUri),
      inject: [CONFIGURACION],
    },
    CierreConexionMongo,
    {
      provide: CONEXION_RABBITMQ,
      useFactory: (configuracion: Configuracion) =>
        crearConexionRabbitmq(configuracion.rabbitmqUrl),
      inject: [CONFIGURACION],
    },
    CierreConexionRabbitmq,
    {
      provide: PublicadorEventosRabbitmq,
      useFactory: (conexion: AmqpConnectionManager, reloj: RelojSistema) =>
        new PublicadorEventosRabbitmq(conexion, reloj),
      inject: [CONEXION_RABBITMQ, RelojSistema],
    },
    {
      provide: EvaluarStockBajoCasoUso,
      useFactory: (
        insumos: RepositorioInsumoMongo,
        publicador: PublicadorEventosRabbitmq,
        reloj: RelojSistema,
      ) => new EvaluarStockBajoCasoUso(insumos, publicador, reloj),
      inject: [RepositorioInsumoMongo, PublicadorEventosRabbitmq, RelojSistema],
    },
    EvaluacionStockBajo,
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
      provide: RepositorioMovimientoMongo,
      useFactory: (conexion: Connection) =>
        new RepositorioMovimientoMongo(conexion.model('MovimientoInventario', esquemaMovimiento)),
      inject: [CONEXION_MONGO],
    },
    {
      provide: RegistrarMovimientoCasoUso,
      useFactory: (
        insumos: RepositorioInsumoMongo,
        movimientos: RepositorioMovimientoMongo,
        unidadTrabajo: UnidadTrabajoMongo,
        auditoria: RegistroAuditoriaMongo,
        reloj: RelojSistema,
      ) => new RegistrarMovimientoCasoUso(insumos, movimientos, unidadTrabajo, auditoria, reloj),
      inject: [
        RepositorioInsumoMongo,
        RepositorioMovimientoMongo,
        UnidadTrabajoMongo,
        RegistroAuditoriaMongo,
        RelojSistema,
      ],
    },
    {
      provide: ConsultarMovimientosCasoUso,
      useFactory: (movimientos: RepositorioMovimientoMongo) =>
        new ConsultarMovimientosCasoUso(movimientos),
      inject: [RepositorioMovimientoMongo],
    },
    {
      provide: CrearInsumoCasoUso,
      useFactory: (
        repositorio: RepositorioInsumoMongo,
        unidadTrabajo: UnidadTrabajoMongo,
        auditoria: RegistroAuditoriaMongo,
        reloj: RelojSistema,
        registrarMovimiento: RegistrarMovimientoCasoUso,
      ) =>
        new CrearInsumoCasoUso(repositorio, unidadTrabajo, auditoria, reloj, registrarMovimiento),
      inject: [
        RepositorioInsumoMongo,
        UnidadTrabajoMongo,
        RegistroAuditoriaMongo,
        RelojSistema,
        RegistrarMovimientoCasoUso,
      ],
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
      provide: ConsultarEstadoInventarioCasoUso,
      useFactory: (repositorio: RepositorioInsumoMongo) =>
        new ConsultarEstadoInventarioCasoUso(repositorio),
      inject: [RepositorioInsumoMongo],
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
