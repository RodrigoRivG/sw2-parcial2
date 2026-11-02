import { mongo } from 'mongoose';
import { crearIndicesAuditoria } from './001-crear-indices-auditoria';
import { crearIndicesInsumos } from './002-crear-indices-insumos';

export interface Migracion {
  nombre: string;
  subir(db: mongo.Db): Promise<void>;
}

/** Migraciones en orden de aplicación. Una migración aplicada no se modifica: se agrega otra. */
export const migraciones: Migracion[] = [crearIndicesAuditoria, crearIndicesInsumos];
