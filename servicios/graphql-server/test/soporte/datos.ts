/**
 * Respuestas de ejemplo copiadas de los contratos reales (DTO de gestión, recursos de operaciones, esquemas de IA y
 * specs de inventario), revisadas en T02.
 */
export const G = '/api/gestion/v1';
export const I = '/api/inventario/v1';
export const O = '/api/operaciones/v1';
export const IA = '/api/ia/v1';

export const pagina = (items: unknown[]) => ({ items, pagina: 0, tamanio: 20, total: items.length });

export const campania = (id: string, idParcela = 'p1', idCultivo = 'cu1') => ({
  id,
  nombre: `Soya verano ${id}`,
  idParcela,
  idCultivo,
  fechaInicio: '2026-11-15',
  fechaFin: '2027-03-30',
  superficieHectareas: '25.5000',
  estado: 'EN_CURSO',
  fechaInicioEjecucion: '2026-11-16T12:00:00.123456Z',
  fechaFinalizacion: null,
  version: 1,
  fechaCreacion: '2026-11-02T14:00:00Z',
  fechaActualizacion: '2026-11-16T12:00:00Z',
});

export const parcela = (id: string) => ({
  id,
  nombre: `Lote ${id}`,
  superficieHectareas: '25.5000',
  ubicacion: 'Km 12, camino a Warnes',
  descripcion: null,
  version: 0,
  fechaCreacion: '2026-11-02T14:00:00Z',
  fechaActualizacion: '2026-11-02T14:00:00Z',
});

export const cultivo = (id: string) => ({
  id,
  nombre: 'Soya',
  variedad: 'Munasqa',
  unidadMedida: 'KILOGRAMO',
  descripcion: null,
  version: 0,
  fechaCreacion: '2026-11-02T14:00:00Z',
  fechaActualizacion: '2026-11-02T14:00:00Z',
});

export const indicadores = (id: string) => ({
  idCampania: id,
  estadoCampania: 'EN_CURSO',
  definitivo: false,
  superficieHectareas: '25.5000',
  produccion: null,
  costoTotal: '820.50',
  rendimientoPorHectarea: null,
  costoPorHectarea: null,
  motivosNoDisponible: ['SIN_PRODUCCION'],
});

export const costos = {
  items: [],
  pagina: 0,
  tamanio: 1,
  total: 3,
  costoTotal: '2320.50',
  subtotalesPorCategoria: { INSUMO: '820.50', MANO_DE_OBRA: '1500.00', MAQUINARIA: '0.00', OTRO: '0.00' },
};

export const historico = {
  idCampania: 'c9',
  idParcela: 'p1',
  nombreParcela: 'Lote Norte',
  superficieHectareas: '25.5000',
  idCultivo: 'cu1',
  nombreCultivo: 'Soya',
  variedad: 'Munasqa',
  fechaInicio: '2026-11-15',
  fechaFin: '2027-03-30',
  fechaInicioEjecucion: '2026-11-16T12:00:00Z',
  fechaFinalizacion: '2027-03-28T18:00:00Z',
  duracionDias: 133,
  produccion: '76500.00',
  fechaCosecha: '2027-03-20',
  costoTotal: '38250.00',
  costosPorCategoria: { INSUMO: '20000.00', MANO_DE_OBRA: '12000.00', MAQUINARIA: '6250.00', OTRO: '0.00' },
  rendimientoPorHectarea: '3000.00',
  costoPorHectarea: '1500.00',
  motivosNoDisponible: [],
};

export const estadoInventario = {
  resumen: { totalInsumos: 3, totalStockBajo: 2 },
  items: [
    {
      idInsumo: 'i1',
      nombre: 'Glifosato',
      categoria: 'FITOSANITARIO',
      unidad: 'LITRO',
      stock: '20.000',
      nivelMinimo: '20.000',
      stockBajo: true,
      fechaUltimaAlerta: '2026-11-02T10:15:00Z',
    },
  ],
  pagina: 0,
  tamanio: 20,
  total: 1,
};

export const insumo = (id: string) => ({
  id,
  nombre: `Urea ${id}`,
  categoria: 'FERTILIZANTE',
  unidad: 'KILOGRAMO',
  stock: '500.000',
  nivelMinimo: '50.000',
  costoUnitario: '4.8500',
  descripcion: 'Bolsa de 50 kg',
  stockBajo: false,
  version: 0,
  fechaCreacion: '2026-11-02T14:00:00Z',
  fechaActualizacion: '2026-11-02T14:00:00Z',
});

export const labor = (id: string, idCampania = 'c1') => ({
  id,
  tipoLabor: 'FERTILIZACION',
  idParcela: 'p1',
  idCampania,
  estado: 'CONFIRMADA',
  fechaReferencia: '2026-11-02T13:30:00Z',
  fechaProgramada: null,
  fechaEjecucion: '2026-11-02T13:30:00Z',
  fechaCreacion: '2026-11-02T13:58:00Z',
  fechaRecepcion: '2026-11-02T14:00:05Z',
  fechaRecepcionEjecucion: '2026-11-02T14:00:05Z',
  responsable: { id: 'sub-ana', nombre: 'Ana Quispe' },
  programadaPor: null,
  observaciones: 'Aplicación al voleo',
  insumos: [{ idInsumo: 'i1', cantidad: '100.000' }],
  validacionCampania: 'VALIDADA',
  idSaga: 's1',
  motivo: null,
  resolucion: null,
  idsSagaAnteriores: [],
  version: 2,
  fechaActualizacion: '2026-11-02T14:00:05Z',
});

export const prediccion = {
  id: 'pr1',
  idCampania: 'c1',
  fecha: '2026-11-04T12:00:00Z',
  cultivo: 'SOYA',
  estadoCampania: 'FINALIZADA',
  origenCostos: 'REGISTRADOS',
  costosPorHectarea: { INSUMO: '2100.00', MANO_DE_OBRA: '350.00', MAQUINARIA: '900.00', OTRO: '150.00' },
  rendimientoEstimado: '3120.40',
  intervalo: { minimo: '2810.00', maximo: '3390.75' },
  produccionEstimada: '79570.20',
  rendimientoReal: '3000.00',
  unidad: 'kg/ha',
  advertencias: [{ codigo: 'FUERA_DE_RANGO', mensaje: 'm', campos: ['OTRO'] }],
  versionModelo: { nombre: 'rendimiento', version: 1 },
  orientativo: true,
  aviso: 'Estimación orientativa basada en datos de referencia. No sustituye una evaluación técnica agrícola.',
};

export const analisis = {
  id: 'an1',
  fecha: '2026-11-04T12:00:00Z',
  filtros: {},
  cantidadAnalizadas: 12,
  truncado: false,
  grupos: [{ grupo: 0, descripcion: 'Costo alto · rendimiento medio', cantidad: 4, idsCampania: ['c1'] }],
  anomalias: [{ idCampania: 'c1', nombreParcela: 'Lote Norte', cultivo: 'MAIZ', puntaje: '-0.12', motivos: ['m'] }],
  excluidas: [{ idCampania: 'c2', motivo: 'SIN_COSTOS' }],
  versionModelo: { nombre: 'patrones', version: 1 },
  orientativo: true,
  aviso: 'Agrupaciones y anomalías orientativas. No sustituyen una evaluación técnica agrícola.',
};
