import { GraphQLError, type ValidationRule } from 'graphql';

/**
 * El esquema solo tiene `Query` (constitución §4). graphql-js no valida que exista el tipo raíz de una `mutation`
 * o `subscription` y fallaría al ejecutarla; esta regla la rechaza en la validación (historia 6, escenario 6).
 */
export const soloConsultas: ValidationRule = (contexto) => ({
  OperationDefinition(nodo) {
    if (nodo.operation !== 'query') {
      contexto.reportError(new GraphQLError('Solo se admiten consultas (query).', { nodes: nodo }));
    }
  },
});
