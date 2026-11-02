export type TipoErrorDominio = 'NO_ENCONTRADO' | 'CONFLICTO' | 'REGLA_NEGOCIO';

/** Error de negocio con un código estable. El dominio no conoce HTTP: el adaptador traduce el tipo. */
export class ErrorDominio extends Error {
  constructor(
    readonly codigo: string,
    mensaje: string,
    readonly tipo: TipoErrorDominio,
    readonly detalles: unknown[] = [],
  ) {
    super(mensaje);
    this.name = 'ErrorDominio';
  }

  static noEncontrado(codigo: string, mensaje: string): ErrorDominio {
    return new ErrorDominio(codigo, mensaje, 'NO_ENCONTRADO');
  }

  static conflicto(codigo: string, mensaje: string): ErrorDominio {
    return new ErrorDominio(codigo, mensaje, 'CONFLICTO');
  }

  static reglaNegocio(codigo: string, mensaje: string, detalles: unknown[] = []): ErrorDominio {
    return new ErrorDominio(codigo, mensaje, 'REGLA_NEGOCIO', detalles);
  }
}
