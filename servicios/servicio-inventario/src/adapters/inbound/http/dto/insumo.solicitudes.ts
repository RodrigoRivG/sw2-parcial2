import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsBoolean,
  IsEnum,
  IsInt,
  IsOptional,
  IsString,
  Length,
  Matches,
  MaxLength,
  Min,
} from 'class-validator';
import { CategoriaInsumo } from '../../../../domain/supply/categoria-insumo.enum';
import { UnidadMedida } from '../../../../domain/supply/unidad-medida.enum';
import { ConsultaPaginada } from './consulta-paginada';
import { ABooleano, PATRON_CANTIDAD, PATRON_COSTO_UNITARIO, Recortar } from './transformaciones';

const MENSAJE_CANTIDAD = 'debe ser un decimal en texto con hasta 3 decimales';
const MENSAJE_COSTO = 'debe ser un decimal en texto con hasta 4 decimales';

class DatosInsumoSolicitud {
  @ApiProperty({ example: 'Urea 46 %', maxLength: 100 })
  @Recortar()
  @IsString()
  @Length(1, 100)
  nombre!: string;

  @ApiProperty({ enum: CategoriaInsumo })
  @IsEnum(CategoriaInsumo)
  categoria!: CategoriaInsumo;

  @ApiProperty({ enum: UnidadMedida })
  @IsEnum(UnidadMedida)
  unidad!: UnidadMedida;

  @ApiProperty({ example: '50', description: 'Decimal en texto, ≥ 0, hasta 3 decimales' })
  @IsString()
  @Matches(PATRON_CANTIDAD, { message: `nivelMinimo ${MENSAJE_CANTIDAD}` })
  nivelMinimo!: string;

  @ApiProperty({ example: '4.85', description: 'BOB, decimal en texto, ≥ 0, hasta 4 decimales' })
  @IsString()
  @Matches(PATRON_COSTO_UNITARIO, { message: `costoUnitario ${MENSAJE_COSTO}` })
  costoUnitario!: string;

  @ApiPropertyOptional({ example: 'Bolsa de 50 kg', maxLength: 500, nullable: true })
  @IsOptional()
  @Recortar()
  @IsString()
  @MaxLength(500)
  descripcion?: string | null;
}

export class CrearInsumoSolicitud extends DatosInsumoSolicitud {
  @ApiPropertyOptional({ example: '500', description: 'Se registra como una entrada; por defecto 0' })
  @IsOptional()
  @IsString()
  @Matches(PATRON_CANTIDAD, { message: `stockInicial ${MENSAJE_CANTIDAD}` })
  stockInicial?: string;
}

export class ActualizarInsumoSolicitud extends DatosInsumoSolicitud {
  @ApiProperty({ example: 0, description: 'La versión recibida al consultar el insumo' })
  @IsInt()
  @Min(0)
  version!: number;
}

export class ConsultaInsumos extends ConsultaPaginada {
  @ApiPropertyOptional({ description: 'Texto contenido en el nombre, sin distinguir mayúsculas' })
  @IsOptional()
  @Recortar()
  @IsString()
  @MaxLength(100)
  nombre?: string;

  @ApiPropertyOptional({ enum: CategoriaInsumo })
  @IsOptional()
  @IsEnum(CategoriaInsumo)
  categoria?: CategoriaInsumo;

  @ApiPropertyOptional({ description: 'Solo insumos con stock mayor a 0' })
  @IsOptional()
  @ABooleano()
  @IsBoolean()
  soloConStock?: boolean;
}
