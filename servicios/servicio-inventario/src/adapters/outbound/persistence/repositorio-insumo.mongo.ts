import { FilterQuery, Model } from 'mongoose';
import { Pagina, Paginacion } from '../../../application/ports/pagina';
import {
  FiltrosInsumos,
  RepositorioInsumo,
} from '../../../application/ports/repositorio-insumo.puerto';
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

function escaparRegex(texto: string): string {
  return texto.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
