package com.agrosystem.gestion.interfaces.rest;

import com.agrosystem.gestion.interfaces.rest.error.SolicitudInvalidaExcepcion;

/** Validación común de la paginación de los listados. */
public record ParametrosPagina(int pagina, int tamanio) {

    public static final int TAMANIO_POR_DEFECTO = 20;
    public static final int TAMANIO_MAXIMO = 100;

    public static ParametrosPagina de(Integer pagina, Integer tamanio) {
        return de(pagina, tamanio, TAMANIO_MAXIMO);
    }

    public static ParametrosPagina de(Integer pagina, Integer tamanio, int tamanioMaximo) {
        int paginaFinal = pagina == null ? 0 : pagina;
        int tamanioFinal = tamanio == null ? TAMANIO_POR_DEFECTO : tamanio;
        if (paginaFinal < 0) {
            throw new SolicitudInvalidaExcepcion("pagina", "Debe ser mayor o igual a 0.");
        }
        if (tamanioFinal < 1 || tamanioFinal > tamanioMaximo) {
            throw new SolicitudInvalidaExcepcion("tamanio", "Debe estar entre 1 y " + tamanioMaximo + ".");
        }
        return new ParametrosPagina(paginaFinal, tamanioFinal);
    }
}
