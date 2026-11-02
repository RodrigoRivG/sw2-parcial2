export interface Paginacion {
  pagina: number;
  tamanio: number;
}

export interface Pagina<T> extends Paginacion {
  items: T[];
  total: number;
}
