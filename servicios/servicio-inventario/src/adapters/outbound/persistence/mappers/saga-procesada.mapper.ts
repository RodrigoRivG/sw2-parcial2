import { ResultadoSagaProcesada } from '../../../../domain/saga/resultado-saga-procesada.enum';
import {
  CodigoRechazoSaga,
  RespuestaDescuento,
  RespuestaRestauracion,
  SagaProcesada,
} from '../../../../domain/saga/saga-procesada.entidad';
import { Cantidad } from '../../../../domain/shared/cantidad.vo';
import { Dinero } from '../../../../domain/shared/dinero.vo';
import {
  DocumentoDescuento,
  DocumentoRestauracion,
  DocumentoSagaProcesada,
} from '../schemas/saga-procesada.esquema';
import { aDecimal128 } from './insumo.mapper';

export function aCamposGuardados(saga: SagaProcesada) {
  return {
    resultado: saga.resultado,
    descuento: saga.descuento ? descuentoADocumento(saga.descuento) : null,
    restauracion: saga.restauracion ? restauracionADocumento(saga.restauracion) : null,
    fecha_actualizacion: saga.fechaActualizacion,
  };
}

export function aDominio(documento: DocumentoSagaProcesada): SagaProcesada {
  return SagaProcesada.reconstruir({
    idSaga: documento._id,
    idLabor: documento.id_labor,
    resultado: (documento.resultado as ResultadoSagaProcesada | null) ?? null,
    descuento: documento.descuento ? descuentoADominio(documento.descuento) : null,
    restauracion: documento.restauracion ? restauracionADominio(documento.restauracion) : null,
    fechaProcesamiento: documento.fecha_procesamiento,
    fechaActualizacion: documento.fecha_actualizacion,
  });
}

function descuentoADocumento(descuento: RespuestaDescuento): DocumentoDescuento {
  if (descuento.tipo === 'InsumosDescontados') {
    return {
      tipo: descuento.tipo,
      costo_total: aDecimal128(descuento.costoTotal.valor.toString()),
      items: descuento.items.map((item) => ({
        id_insumo: item.idInsumo,
        cantidad: aDecimal128(item.cantidad.valor.toString()),
        costo_unitario: aDecimal128(item.costoUnitario.valor.toString()),
      })),
    };
  }
  return {
    tipo: descuento.tipo,
    codigo: descuento.codigo,
    motivo: descuento.motivo,
    insumos_afectados: descuento.insumosAfectados.map((afectado) => ({
      id_insumo: afectado.idInsumo,
      cantidad_solicitada: afectado.cantidadSolicitada,
      stock_disponible: afectado.stockDisponible,
    })),
  };
}

function descuentoADominio(documento: DocumentoDescuento): RespuestaDescuento {
  if (documento.tipo === 'InsumosDescontados') {
    return {
      tipo: documento.tipo,
      costoTotal: Dinero.desdeAlmacen(String(documento.costo_total)),
      items: (documento.items ?? []).map((item) => ({
        idInsumo: item.id_insumo,
        cantidad: Cantidad.desdeAlmacen(String(item.cantidad)),
        costoUnitario: Dinero.desdeAlmacen(String(item.costo_unitario)),
      })),
    };
  }
  return {
    tipo: documento.tipo,
    codigo: documento.codigo as CodigoRechazoSaga,
    motivo: documento.motivo ?? '',
    insumosAfectados: (documento.insumos_afectados ?? []).map((afectado) => ({
      idInsumo: afectado.id_insumo,
      cantidadSolicitada: afectado.cantidad_solicitada,
      stockDisponible: afectado.stock_disponible,
    })),
  };
}

function restauracionADocumento(restauracion: RespuestaRestauracion): DocumentoRestauracion {
  return {
    sin_efecto: restauracion.sinEfecto,
    items: restauracion.items.map((item) => ({
      id_insumo: item.idInsumo,
      cantidad: aDecimal128(item.cantidad.valor.toString()),
    })),
  };
}

function restauracionADominio(documento: DocumentoRestauracion): RespuestaRestauracion {
  return {
    sinEfecto: documento.sin_efecto,
    items: documento.items.map((item) => ({
      idInsumo: item.id_insumo,
      cantidad: Cantidad.desdeAlmacen(String(item.cantidad)),
    })),
  };
}
