import { Types } from 'mongoose';
import { Cantidad } from '../../../../domain/shared/cantidad.vo';
import { Dinero } from '../../../../domain/shared/dinero.vo';
import { CategoriaInsumo } from '../../../../domain/supply/categoria-insumo.enum';
import { Insumo } from '../../../../domain/supply/insumo.entidad';
import { UnidadMedida } from '../../../../domain/supply/unidad-medida.enum';
import { DocumentoInsumo } from '../schemas/insumo.esquema';

export function normalizarNombre(nombre: string): string {
  return nombre.trim().toLowerCase();
}

export function aDecimal128(texto: string): Types.Decimal128 {
  return Types.Decimal128.fromString(texto);
}

/** Campos editables del insumo, tal como se guardan. */
export function aCamposEditables(insumo: Insumo) {
  return {
    nombre: insumo.nombre,
    nombre_normalizado: normalizarNombre(insumo.nombre),
    categoria: insumo.categoria,
    unidad: insumo.unidad,
    nivel_minimo: aDecimal128(insumo.nivelMinimo.valor.toString()),
    costo_unitario: aDecimal128(insumo.costoUnitario.valor.toString()),
    descripcion: insumo.descripcion,
    fecha_actualizacion: insumo.fechaActualizacion,
  };
}

export function aDocumento(insumo: Insumo): DocumentoInsumo {
  return {
    _id: insumo.id,
    ...aCamposEditables(insumo),
    stock: aDecimal128(insumo.stock.valor.toString()),
    tiene_movimientos: insumo.tieneMovimientos,
    fecha_ultima_alerta: insumo.fechaUltimaAlerta,
    reserva_alerta_hasta: insumo.reservaAlertaHasta,
    version: insumo.version,
    fecha_creacion: insumo.fechaCreacion,
  };
}

export function aDominio(documento: DocumentoInsumo): Insumo {
  const unidad = documento.unidad as UnidadMedida;
  return Insumo.reconstruir({
    id: documento._id,
    nombre: documento.nombre,
    categoria: documento.categoria as CategoriaInsumo,
    unidad,
    stock: Cantidad.de(documento.stock.toString(), unidad),
    nivelMinimo: Cantidad.de(documento.nivel_minimo.toString(), unidad),
    costoUnitario: Dinero.costoUnitario(documento.costo_unitario.toString()),
    descripcion: documento.descripcion ?? null,
    tieneMovimientos: documento.tiene_movimientos,
    fechaUltimaAlerta: documento.fecha_ultima_alerta ?? null,
    reservaAlertaHasta: documento.reserva_alerta_hasta ?? null,
    version: documento.version,
    fechaCreacion: documento.fecha_creacion,
    fechaActualizacion: documento.fecha_actualizacion,
  });
}
