import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsEnum, IsISO8601, IsOptional, IsString, IsUUID, Length, Matches } from 'class-validator';
import { TipoMovimiento } from '../../../../domain/movement/tipo-movimiento.enum';
import { ConsultaPaginada } from './consulta-paginada';
import { PATRON_CANTIDAD, Recortar } from './transformaciones';

export class RegistrarMovimientoSolicitud {
  @ApiProperty({ format: 'uuid' })
  @IsUUID()
  idInsumo!: string;

  @ApiProperty({ enum: TipoMovimiento })
  @IsEnum(TipoMovimiento)
  tipo!: TipoMovimiento;

  @ApiProperty({
    example: '80',
    description: 'Decimal en texto, > 0, en la unidad del insumo, hasta 3 decimales',
  })
  @IsString()
  @Matches(PATRON_CANTIDAD, { message: 'cantidad debe ser un decimal en texto con hasta 3 decimales' })
  cantidad!: string;

  @ApiProperty({ example: 'Compra factura 1234', maxLength: 200 })
  @Recortar()
  @IsString()
  @Length(1, 200)
  motivo!: string;
}

export class ConsultaMovimientos extends ConsultaPaginada {
  @ApiPropertyOptional({ format: 'uuid' })
  @IsOptional()
  @IsUUID()
  idInsumo?: string;

  @ApiPropertyOptional({ enum: TipoMovimiento })
  @IsOptional()
  @IsEnum(TipoMovimiento)
  tipo?: TipoMovimiento;

  @ApiPropertyOptional({ format: 'uuid' })
  @IsOptional()
  @IsUUID()
  idSaga?: string;

  @ApiPropertyOptional({
    example: '2026-11-01T00:00:00Z',
    description: 'Desde este instante, inclusive (ISO 8601; una fecha sin hora es las 00:00 UTC)',
  })
  @IsOptional()
  @IsISO8601({ strict: true })
  desde?: string;

  @ApiPropertyOptional({
    example: '2026-11-30T23:59:59Z',
    description: 'Hasta este instante, inclusive',
  })
  @IsOptional()
  @IsISO8601({ strict: true })
  hasta?: string;
}
