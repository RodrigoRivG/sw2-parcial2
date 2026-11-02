import { FilterQuery, Model } from 'mongoose';
import { Pagina, Paginacion } from '../../../application/ports/pagina';
import {
  EstadoInventario,
  FiltrosEstadoInventario,
  FiltrosInsumos,
  RepositorioInsumo,
} from '../../../application/ports/repositorio-insumo.puerto';
import { TipoMovimiento } from '../../../domain/movement/tipo-movimiento.enum';
import { Cantidad } from '../../../domain/shared/cantidad.vo';
import { nombreInsumoDuplicado } from '../../../domain/supply/errores-insumo';
import { Insumo } from '../../../domain/supply/insumo.entidad';
import { esClaveDuplicada, opcionesSesion } from './contexto-sesion';
import {
  aCamposEditables,
  aDecimal128,
  aDocumento,
  aDominio,
  normalizarNombre,
} from './mappers/insumo.mapper';
import { DocumentoInsumo } from './schemas/insumo.esquema';

export class RepositorioInsumoMongo implements RepositorioInsumo {
  constructor(private readonly modelo: Model<DocumentoInsumo>) {}

  async guardarNuevo(insumo: Insumo): Promise<void> {
    try {
      await this.modelo.insertMany([aDocumento(insumo)], opcionesSesion());
    } catch (error) {
      throw esClaveDuplicada(error) ? nombreInsumoDuplicado() : error;
    }
  }

  async actualizarSiVersion(insumo: Insumo, versionEsperada: number): Promise<boolean> {
    try {
      const resultado = await this.modelo.updateOne(
        { _id: insumo.id, version: versionEsperada },
        { $set: aCamposEditables(insumo), $inc: { version: 1 } },
        opcionesSesion(),
      );
      return resultado.matchedCount === 1;
    } catch (error) {
      throw esClaveDuplicada(error) ? nombreInsumoDuplicado() : error;
    }
  }

  async buscarPorId(id: string): Promise<Insumo | null> {
    const documento = await this.modelo
      .findOne({ _id: id }, null, opcionesSesion())
      .lean<DocumentoInsumo>()
      .exec();
    return documento ? aDominio(documento) : null;
  }

  async aplicarMovimiento(
    id: string,
    tipo: TipoMovimiento,
    cantidad: Cantidad,
    ahora: Date,
  ): Promise<Cantidad | null> {
    const texto = cantidad.valor.toString();
    const esSalida = tipo === TipoMovimiento.SALIDA;
    // Actualización atómica condicionada: una salida nunca deja stock negativo (constitución §4).
    const documento = await this.modelo
      .findOneAndUpdate(
        esSalida ? { _id: id, stock: { $gte: aDecimal128(texto) } } : { _id: id },
        {
          $inc: { stock: aDecimal128(esSalida ? `-${texto}` : texto) },
          $set: { tiene_movimientos: true, fecha_actualizacion: ahora },
        },
        { ...opcionesSesion(), returnDocument: 'after' },
      )
      .lean<DocumentoInsumo>()
      .exec();
    return documento ? Cantidad.desdeAlmacen(documento.stock.toString()) : null;
  }

  async reservarAlerta(
    id: string,
    fechaUltimaAlertaLeida: Date | null,
    ahora: Date,
    reservaHasta: Date,
  ): Promise<boolean> {
    const resultado = await this.modelo.updateOne(
      {
        _id: id,
        fecha_ultima_alerta: fechaUltimaAlertaLeida,
        $or: [{ reserva_alerta_hasta: null }, { reserva_alerta_hasta: { $lte: ahora } }],
      },
      { $set: { reserva_alerta_hasta: reservaHasta } },
      opcionesSesion(),
    );
    return resultado.modifiedCount === 1;
  }

  async confirmarAlerta(id: string, fecha: Date): Promise<void> {
    await this.modelo.updateOne(
      { _id: id },
      { $set: { fecha_ultima_alerta: fecha, reserva_alerta_hasta: null } },
      opcionesSesion(),
    );
  }

  async liberarReserva(id: string): Promise<void> {
    await this.modelo.updateOne(
      { _id: id },
      { $set: { reserva_alerta_hasta: null } },
      opcionesSesion(),
    );
  }

  async consultarEstado(
    filtros: FiltrosEstadoInventario,
    paginacion: Paginacion,
  ): Promise<EstadoInventario> {
    // Replica en MongoDB la regla de politica-stock-bajo.ts para ordenar y contar;
    // el stockBajo de la respuesta lo calcula el dominio.
    const soloBajos = filtros.soloStockBajo ? [{ $match: { stock_bajo: true } }] : [];
    const [resultado] = await this.modelo
      .aggregate<ResultadoEstado>([
        { $match: filtros.categoria ? { categoria: filtros.categoria } : {} },
        { $addFields: { stock_bajo: { $lte: ['$stock', '$nivel_minimo'] } } },
        {
          $facet: {
            resumen: [
              {
                $group: {
                  _id: null,
                  total: { $sum: 1 },
                  total_bajo: { $sum: { $cond: ['$stock_bajo', 1, 0] } },
                },
              },
            ],
            pagina: [
              ...soloBajos,
              { $sort: { stock_bajo: -1, nombre_normalizado: 1, _id: 1 } },
              { $skip: paginacion.pagina * paginacion.tamanio },
              { $limit: paginacion.tamanio },
            ],
            total: [...soloBajos, { $count: 'n' }],
          },
        },
      ])
      .exec();
    const resumen = resultado?.resumen[0];
    return {
      ...paginacion,
      items: (resultado?.pagina ?? []).map(aDominio),
      total: resultado?.total[0]?.n ?? 0,
      resumen: { totalInsumos: resumen?.total ?? 0, totalStockBajo: resumen?.total_bajo ?? 0 },
    };
  }

  async listar(filtros: FiltrosInsumos, paginacion: Paginacion): Promise<Pagina<Insumo>> {
    const filtro: FilterQuery<DocumentoInsumo> = {};
    if (filtros.nombre?.trim()) {
      filtro.nombre_normalizado = { $regex: escaparRegex(normalizarNombre(filtros.nombre)) };
    }
    if (filtros.categoria) {
      filtro.categoria = filtros.categoria;
    }
    if (filtros.soloConStock) {
      filtro.stock = { $gt: aDecimal128('0') };
    }
    const [documentos, total] = await Promise.all([
      this.modelo
        .find(filtro, null, opcionesSesion())
        .sort({ nombre_normalizado: 1, _id: 1 })
        .skip(paginacion.pagina * paginacion.tamanio)
        .limit(paginacion.tamanio)
        .lean<DocumentoInsumo[]>()
        .exec(),
      this.modelo.countDocuments(filtro, opcionesSesion()).exec(),
    ]);
    return { ...paginacion, items: documentos.map(aDominio), total };
  }
}

interface ResultadoEstado {
  resumen: { total: number; total_bajo: number }[];
  pagina: DocumentoInsumo[];
  total: { n: number }[];
}

function escaparRegex(texto: string): string {
  return texto.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
