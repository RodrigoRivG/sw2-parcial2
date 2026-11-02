import { ApiProperty } from '@nestjs/swagger';
import { CategoriaInsumo } from '../../../../domain/supply/categoria-insumo.enum';
import { Insumo } from '../../../../domain/supply/insumo.entidad';
import { UnidadMedida } from '../../../../domain/supply/unidad-medida.enum';

/** Vista para `tecnico_campo`: sin costo unitario ni otros datos de gestión. */
export class InsumoReducidoRespuesta {
  @ApiProperty() id!: string;
  @ApiProperty() nombre!: string;
  @ApiProperty({ enum: CategoriaInsumo }) categoria!: CategoriaInsumo;
  @ApiProperty({ enum: UnidadMedida }) unidad!: UnidadMedida;
  @ApiProperty({ example: '500.000' }) stock!: string;
}

export class InsumoRespuesta extends InsumoReducidoRespuesta {
  @ApiProperty({ example: '50.000' }) nivelMinimo!: string;
  @ApiProperty({ example: '4.8500', description: 'BOB' }) costoUnitario!: string;
  @ApiProperty({ nullable: true, type: String }) descripcion!: string | null;
  @ApiProperty() stockBajo!: boolean;
  @ApiProperty() version!: number;
  @ApiProperty() fechaCreacion!: string;
  @ApiProperty() fechaActualizacion!: string;
}

export function aRespuestaReducida(insumo: Insumo): InsumoReducidoRespuesta {
  return {
    id: insumo.id,
    nombre: insumo.nombre,
    categoria: insumo.categoria,
    unidad: insumo.unidad,
    stock: insumo.stock.aTexto(),
  };
}

export function aRespuesta(insumo: Insumo): InsumoRespuesta {
  return {
    ...aRespuestaReducida(insumo),
    nivelMinimo: insumo.nivelMinimo.aTexto(),
    costoUnitario: insumo.costoUnitario.aTextoCostoUnitario(),
    descripcion: insumo.descripcion,
    stockBajo: insumo.stockBajo,
    version: insumo.version,
    fechaCreacion: insumo.fechaCreacion.toISOString(),
    fechaActualizacion: insumo.fechaActualizacion.toISOString(),
  };
}
