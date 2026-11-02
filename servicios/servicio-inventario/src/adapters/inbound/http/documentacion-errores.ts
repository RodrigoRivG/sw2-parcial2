import { applyDecorators } from '@nestjs/common';
import { ApiResponse } from '@nestjs/swagger';

/** Documenta en OpenAPI las respuestas de error de un endpoint: `[estado, códigos]`. */
export function ApiErrores(...errores: [number, string][]) {
  return applyDecorators(
    ...errores.map(([status, codigos]) =>
      ApiResponse({ status, description: `Formato común de error. Código: ${codigos}` }),
    ),
  );
}
