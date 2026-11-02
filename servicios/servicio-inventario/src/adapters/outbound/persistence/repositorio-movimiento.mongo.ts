import { FilterQuery, Model } from 'mongoose';
import { Pagina, Paginacion } from '../../../application/ports/pagina';
import {
  FiltrosMovimientos,
  RepositorioMovimiento,
} from '../../../application/ports/repositorio-movimiento.puerto';
import { MovimientoInventario } from '../../../domain/movement/movimiento-inventario.entidad';
import { TipoMovimiento } from '../../../domain/movement/tipo-movimiento.enum';
import { opcionesSesion } from './contexto-sesion';
import { aDocumento, aDominio } from './mappers/movimiento.mapper';
import { DocumentoMovimiento } from './schemas/movimiento-inventario.esquema';

export class RepositorioMovimientoMongo implements RepositorioMovimiento {
  constructor(private readonly modelo: Model<DocumentoMovimiento>) {}

  async guardar(movimiento: MovimientoInventario): Promise<void> {
    await this.modelo.insertMany([aDocumento(movimiento)], opcionesSesion());
  }

  async buscarPorId(id: string): Promise<MovimientoInventario | null> {
    const documento = await this.modelo
      .findOne({ _id: id }, null, opcionesSesion())
      .lean<DocumentoMovimiento>()
      .exec();
    return documento ? aDominio(documento) : null;
  }

  async listarPorSaga(idSaga: string, tipo: TipoMovimiento): Promise<MovimientoInventario[]> {
    const documentos = await this.modelo
      .find({ id_saga: idSaga, tipo }, null, opcionesSesion())
      .sort({ fecha: 1, _id: 1 })
      .lean<DocumentoMovimiento[]>()
      .exec();
    return documentos.map(aDominio);
  }

  async listar(
    filtros: FiltrosMovimientos,
    paginacion: Paginacion,
  ): Promise<Pagina<MovimientoInventario>> {
    const filtro: FilterQuery<DocumentoMovimiento> = {};
    if (filtros.idInsumo) {
      filtro.id_insumo = filtros.idInsumo;
    }
    if (filtros.tipo) {
      filtro.tipo = filtros.tipo;
    }
    if (filtros.idSaga) {
      filtro.id_saga = filtros.idSaga;
    }
    if (filtros.desde || filtros.hasta) {
      filtro.fecha = {
        ...(filtros.desde ? { $gte: filtros.desde } : {}),
        ...(filtros.hasta ? { $lte: filtros.hasta } : {}),
      };
    }
    const [documentos, total] = await Promise.all([
      this.modelo
        .find(filtro, null, opcionesSesion())
        .sort({ fecha: -1, _id: -1 })
        .skip(paginacion.pagina * paginacion.tamanio)
        .limit(paginacion.tamanio)
        .lean<DocumentoMovimiento[]>()
        .exec(),
      this.modelo.countDocuments(filtro, opcionesSesion()).exec(),
    ]);
    return { ...paginacion, items: documentos.map(aDominio), total };
  }
}
