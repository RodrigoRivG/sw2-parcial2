import { ApiPropertyOptional } from '@nestjs/swagger';
import { Type } from 'class-transformer';
import { IsInt, Max, Min } from 'class-validator';

export class ConsultaPaginada {
  @ApiPropertyOptional({ default: 0, minimum: 0 })
  @Type(() => Number)
  @IsInt()
  @Min(0)
  pagina = 0;

  @ApiPropertyOptional({ default: 20, minimum: 1, maximum: 100 })
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  tamanio = 20;
}

export interface PaginaRespuesta<T> {
  items: T[];
  pagina: number;
  tamanio: number;
  total: number;
}
