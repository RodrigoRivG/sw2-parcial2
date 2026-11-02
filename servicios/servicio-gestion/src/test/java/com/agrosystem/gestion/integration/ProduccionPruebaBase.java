package com.agrosystem.gestion.integration;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.UUID;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.ResultActions;

abstract class ProduccionPruebaBase extends CostoCampaniaPruebaBase {

    /** La fecha de cosecha debe estar entre el inicio de la campaña y hoy: el inicio queda en el pasado. */
    static final LocalDate DIA_ACTUAL = LocalDate.now(ZoneOffset.UTC);
    static final String INICIO_PASADO = DIA_ACTUAL.minusDays(30).toString();
    static final String FIN_FUTURO = DIA_ACTUAL.plusDays(30).toString();

    protected String crearCampaniaIniciable(String nombre) throws Exception {
        return crearEn(RUTA, cuerpo(nombre, idParcela, idCultivo, INICIO_PASADO, FIN_FUTURO));
    }

    protected String crearCampaniaEnCurso(String nombre) throws Exception {
        String id = crearCampaniaIniciable(nombre);
        iniciar(id);
        return id;
    }

    protected String rutaProduccion(String idCampania) {
        return RUTA + "/" + idCampania + "/produccion";
    }

    protected String cuerpoProduccion(String cantidad, String fecha) {
        return "{\"cantidad\": \"" + cantidad + "\", \"fechaCosecha\": \"" + fecha
                + "\", \"observaciones\": \"Peso de balanza\"}";
    }

    protected ResultActions registrarProduccion(String idCampania, String cuerpo, String rol) throws Exception {
        return mockMvc.perform(put(rutaProduccion(idCampania)).with(conRol(rol))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpo));
    }

    protected long versionDe(String idCampania) {
        return campanias.findById(UUID.fromString(idCampania)).orElseThrow().getVersion();
    }

    protected ResultActions finalizar(String idCampania) throws Exception {
        return mockMvc.perform(put(RUTA + "/" + idCampania + "/estado").with(conRol("administrador"))
                .contentType(MediaType.APPLICATION_JSON)
                .content(cuerpoEstado("FINALIZADA", versionDe(idCampania))));
    }
}
