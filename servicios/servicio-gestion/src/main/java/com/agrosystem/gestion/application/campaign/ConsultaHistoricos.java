package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.shared.Pagina;

/** Puerto de lectura; devuelve filas planas, no agregados. */
public interface ConsultaHistoricos {

    Pagina<FilaHistorico> listar(FiltrosHistoricos filtros, int pagina, int tamanio);
}
