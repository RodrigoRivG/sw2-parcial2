import { GraphQLError, GraphQLScalarType, Kind } from 'graphql';

/**
 * Escalares de texto (constitución §4): el valor del servicio pasa sin cambios; solo se verifica su formato.
 * Un número JSON nunca es un `Decimal` válido.
 */
function escalarDeTexto(nombre: string, descripcion: string, formato: RegExp): GraphQLScalarType {
  const validar = (valor: unknown): string => {
    if (typeof valor !== 'string' || !formato.test(valor)) {
      throw new GraphQLError(`${nombre} inválido: ${JSON.stringify(valor)}`);
    }
    return valor;
  };
  return new GraphQLScalarType({
    name: nombre,
    description: descripcion,
    serialize: validar,
    parseValue: validar,
    parseLiteral: (nodo) => {
      if (nodo.kind !== Kind.STRING) {
        throw new GraphQLError(`${nombre} debe escribirse como texto`);
      }
      return validar(nodo.value);
    },
  });
}

export const Decimal = escalarDeTexto('Decimal', 'Decimal exacto como texto ("820.50")', /^-?\d+(\.\d+)?$/);
export const Fecha = escalarDeTexto('Fecha', 'Fecha sin hora, AAAA-MM-DD', /^\d{4}-\d{2}-\d{2}$/);
export const FechaHora = escalarDeTexto(
  'FechaHora',
  'Fecha y hora ISO 8601 UTC',
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/,
);
