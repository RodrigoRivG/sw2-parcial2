import { Transform } from 'class-transformer';

/** Cantidad en texto: el signo se acepta aquí para que el dominio responda el 422 correspondiente. */
export const PATRON_CANTIDAD = /^-?\d{1,12}(\.\d{1,3})?$/;
export const PATRON_COSTO_UNITARIO = /^-?\d{1,12}(\.\d{1,4})?$/;

export const Recortar = () =>
  Transform(({ value }) => (typeof value === 'string' ? value.trim() : value));

/** `"true"` / `"false"` de la query string a booleano; otro valor queda igual y lo rechaza `@IsBoolean`. */
export const ABooleano = () =>
  Transform(({ value }) => (value === 'true' ? true : value === 'false' ? false : value));
