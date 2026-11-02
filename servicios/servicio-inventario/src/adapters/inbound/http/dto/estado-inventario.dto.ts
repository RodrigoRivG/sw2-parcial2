import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsBoolean, IsEnum, IsOptional } from 'class-validator';
import { CategoriaInsumo } from '../../../../domain/supply/categoria-insumo.enum';
import { Insumo } from '../../../../domain/supply/insumo.entidad';
import { UnidadMedida } from '../../../../domain/supply/unidad-medida.enum';
import { ConsultaPaginada } from './consulta-paginada';
import { ABooleano } from './transformaciones';

export class ConsultaEstadoInventario extends ConsultaPaginada {
  @ApiPropertyOptional({ enum: CategoriaInsumo, description: 'También acota el resumen' })
  @IsOptional()
  @IsEnum(CategoriaInsumo)
  categoria?: CategoriaInsumo;

  @ApiPropertyOptional({ description: 'Solo insumos en stock bajo; no cambia el resumen' })
  @IsOptional()
  @ABooleano()
  @IsBoolean()
  soloStockBajo?: boolean;
}

/** Sin datos económicos (RQ-EST-07): quien necesite el costo usa GET /insumos. */
export class EstadoInsumoRespuesta {
  @ApiProperty() idInsumo!: string;
  @ApiProperty() nombre!: string;
  @ApiProperty({ enum: CategoriaInsumo }) categoria!: CategoriaInsumo;
  @ApiProperty({ enum: UnidadMedida }) unidad!: UnidadMedida;
  @ApiProperty({ example: '20.000' }) stock!: string;
  @ApiProperty({ example: '20.000' }) nivelMinimo!: string;
  @ApiProperty({ description: 'stock <= nivelMinimo (RN-05)' }) stockBajo!: boolean;
  @ApiProperty({ nullable: true, type: String }) fechaUltimaAlerta!: string | null;
}

export class ResumenEstadoRespuesta {
  @ApiProperty() totalInsumos!: number;
  @ApiProperty() totalStockBajo!: number;
}

export class EstadoInventarioRespuesta {
  @ApiProperty({ type: ResumenEstadoRespuesta }) resumen!: ResumenEstadoRespuesta;
  @ApiProperty({ type: [EstadoInsumoRespuesta] }) items!: EstadoInsumoRespuesta[];
  @ApiProperty() pagina!: number;
  @ApiProperty() tamanio!: number;
  @ApiProperty() total!: number;
}

export function aEstadoInsumo(insumo: Insumo): EstadoInsumoRespuesta {
  return {
    idInsumo: insumo.id,
    nombre: insumo.nombre,
    categoria: insumo.categoria,
    unidad: insumo.unidad,
    stock: insumo.stock.aTexto(),
    nivelMinimo: insumo.nivelMinimo.aTexto(),
    stockBajo: insumo.stockBajo,
    fechaUltimaAlerta: insumo.fechaUltimaAlerta?.toISOString() ?? null,
  };
}
