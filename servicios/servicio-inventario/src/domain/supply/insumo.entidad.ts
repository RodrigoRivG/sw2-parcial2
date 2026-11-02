import { Cantidad } from '../shared/cantidad.vo';
import { ValorDecimal } from '../shared/decimal';
import { Dinero } from '../shared/dinero.vo';
import { ErrorDominio } from '../shared/error-dominio';
import { CategoriaInsumo } from './categoria-insumo.enum';
import { estaEnStockBajo } from './politica-stock-bajo';
import { UnidadMedida } from './unidad-medida.enum';

/** Datos editables de un insumo. El stock no está: solo cambia mediante movimientos. */
export interface DatosInsumo {
  nombre: string;
  categoria: CategoriaInsumo;
  unidad: UnidadMedida;
  nivelMinimo: ValorDecimal;
  costoUnitario: ValorDecimal;
  descripcion?: string | null;
}

export interface PropiedadesInsumo {
  id: string;
  nombre: string;
  categoria: CategoriaInsumo;
  unidad: UnidadMedida;
  stock: Cantidad;
  nivelMinimo: Cantidad;
  costoUnitario: Dinero;
  descripcion: string | null;
  tieneMovimientos: boolean;
  fechaUltimaAlerta: Date | null;
  version: number;
  fechaCreacion: Date;
  fechaActualizacion: Date;
}

export class Insumo {
  private constructor(private props: PropiedadesInsumo) {}

  /** Insumo nuevo, con stock 0: el stock inicial se registra después como una entrada. */
  static crear(id: string, datos: DatosInsumo, ahora: Date): Insumo {
    return new Insumo({
      id,
      ...Insumo.validar(datos),
      stock: Cantidad.cero(),
      tieneMovimientos: false,
      fechaUltimaAlerta: null,
      version: 0,
      fechaCreacion: ahora,
      fechaActualizacion: ahora,
    });
  }

  static reconstruir(props: PropiedadesInsumo): Insumo {
    return new Insumo({ ...props });
  }

  actualizar(datos: DatosInsumo, ahora: Date): void {
    if (datos.unidad !== this.props.unidad && this.props.tieneMovimientos) {
      throw ErrorDominio.reglaNegocio(
        'UNIDAD_NO_MODIFICABLE',
        'La unidad no se puede cambiar porque el insumo ya tiene movimientos.',
      );
    }
    this.props = { ...this.props, ...Insumo.validar(datos), fechaActualizacion: ahora };
  }

  private static validar(datos: DatosInsumo) {
    return {
      nombre: datos.nombre.trim(),
      categoria: datos.categoria,
      unidad: datos.unidad,
      nivelMinimo: Cantidad.de(datos.nivelMinimo, datos.unidad, 'NIVEL_MINIMO_INVALIDO'),
      costoUnitario: Dinero.costoUnitario(datos.costoUnitario),
      descripcion: datos.descripcion?.trim() || null,
    };
  }

  get id(): string {
    return this.props.id;
  }
  get nombre(): string {
    return this.props.nombre;
  }
  get categoria(): CategoriaInsumo {
    return this.props.categoria;
  }
  get unidad(): UnidadMedida {
    return this.props.unidad;
  }
  get stock(): Cantidad {
    return this.props.stock;
  }
  get nivelMinimo(): Cantidad {
    return this.props.nivelMinimo;
  }
  get costoUnitario(): Dinero {
    return this.props.costoUnitario;
  }
  get descripcion(): string | null {
    return this.props.descripcion;
  }
  get tieneMovimientos(): boolean {
    return this.props.tieneMovimientos;
  }
  get fechaUltimaAlerta(): Date | null {
    return this.props.fechaUltimaAlerta;
  }
  get version(): number {
    return this.props.version;
  }
  get fechaCreacion(): Date {
    return this.props.fechaCreacion;
  }
  get fechaActualizacion(): Date {
    return this.props.fechaActualizacion;
  }
  get stockBajo(): boolean {
    return estaEnStockBajo(this.props.stock, this.props.nivelMinimo);
  }
}
