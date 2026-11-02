import { Reloj } from '../../application/ports/reloj.puerto';

export class RelojSistema implements Reloj {
  ahora(): Date {
    return new Date();
  }
}
