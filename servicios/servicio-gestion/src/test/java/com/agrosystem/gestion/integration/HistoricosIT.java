package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.test.web.servlet.ResultActions;

class HistoricosIT extends ProduccionPruebaBase {

    private static final String RUTA_HISTORICOS = RUTA + "/historicos";

    private ResultActions listar(String consulta) throws Exception {
        return mockMvc.perform(get(RUTA_HISTORICOS + consulta).with(conRol("lectura_gestion")));
    }

    private String crearFinalizadaReal(String nombre, String produccion) throws Exception {
        idParcela = crearParcela("Parcela de " + nombre, "25.5");
        String id = crearCampaniaEnCurso(nombre);
        registrarProduccion(id, cuerpoProduccion(produccion, HOY), "administrador").andExpect(status().isOk());
        return id;
    }

    private void fijarFinalizacion(String id, String instante) {
        jdbc.update("UPDATE campania SET fecha_finalizacion = ? WHERE id = ?",
                Timestamp.from(Instant.parse(instante)), UUID.fromString(id));
    }

    @Test
    void soloDevuelveFinalizadasConTodosSusCampos() throws Exception {
        crearCampaniaEnCurso("En curso");
        String id = crearFinalizadaReal("Soya", "76500");
        registrarCosto(id, "MANO_DE_OBRA", "12000.00");
        registrarCosto(id, "MAQUINARIA", "6250.00");
        insertarCostoSaga(id, "20000.00", false);
        insertarCostoSaga(id, "999.00", true);
        finalizar(id).andExpect(status().isOk());

        listar("")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.items[0].idCampania").value(id))
                .andExpect(jsonPath("$.items[0].idParcela").value(idParcela))
                .andExpect(jsonPath("$.items[0].nombreParcela").value("Parcela de Soya"))
                .andExpect(jsonPath("$.items[0].superficieHectareas").value("25.5000"))
                .andExpect(jsonPath("$.items[0].idCultivo").value(idCultivo))
                .andExpect(jsonPath("$.items[0].nombreCultivo").value("Soya"))
                .andExpect(jsonPath("$.items[0].variedad").value(nullValue()))
                .andExpect(jsonPath("$.items[0].fechaInicio").value(INICIO_PASADO))
                .andExpect(jsonPath("$.items[0].fechaFin").value(FIN_FUTURO))
                .andExpect(jsonPath("$.items[0].fechaInicioEjecucion").isNotEmpty())
                .andExpect(jsonPath("$.items[0].fechaFinalizacion").isNotEmpty())
                .andExpect(jsonPath("$.items[0].duracionDias").value(30))
                .andExpect(jsonPath("$.items[0].produccion").value("76500.00"))
                .andExpect(jsonPath("$.items[0].fechaCosecha").value(HOY))
                .andExpect(jsonPath("$.items[0].costoTotal").value("38250.00"))
                .andExpect(jsonPath("$.items[0].costosPorCategoria.INSUMO").value("20000.00"))
                .andExpect(jsonPath("$.items[0].costosPorCategoria.MANO_DE_OBRA").value("12000.00"))
                .andExpect(jsonPath("$.items[0].costosPorCategoria.MAQUINARIA").value("6250.00"))
                .andExpect(jsonPath("$.items[0].costosPorCategoria.OTRO").value("0.00"))
                .andExpect(jsonPath("$.items[0].rendimientoPorHectarea").value("3000.00"))
                .andExpect(jsonPath("$.items[0].costoPorHectarea").value("1500.00"))
                .andExpect(jsonPath("$.items[0].motivosNoDisponible", empty()));
    }

    @Test
    void finalizadaSinCostosInformaElMotivo() throws Exception {
        String id = crearFinalizadaReal("Sin costos", "100");
        finalizar(id).andExpect(status().isOk());

        listar("")
                .andExpect(jsonPath("$.items[0].costoTotal").value("0.00"))
                .andExpect(jsonPath("$.items[0].costosPorCategoria.INSUMO").value("0.00"))
                .andExpect(jsonPath("$.items[0].produccion").value("100.00"))
                .andExpect(jsonPath("$.items[0].rendimientoPorHectarea").value(nullValue()))
                .andExpect(jsonPath("$.items[0].costoPorHectarea").value(nullValue()))
                .andExpect(jsonPath("$.items[0].motivosNoDisponible", contains("SIN_COSTOS")));
    }

    @Test
    void ordenaPorFechaDeFinalizacionDescendenteYPagina() throws Exception {
        String antigua = crearFinalizadaReal("Antigua", "1");
        finalizar(antigua).andExpect(status().isOk());
        String reciente = crearFinalizadaReal("Reciente", "1");
        finalizar(reciente).andExpect(status().isOk());
        fijarFinalizacion(antigua, "2026-01-10T12:00:00Z");
        fijarFinalizacion(reciente, "2026-06-10T12:00:00Z");

        listar("")
                .andExpect(jsonPath("$.items[0].idCampania").value(reciente))
                .andExpect(jsonPath("$.items[1].idCampania").value(antigua));
        listar("?tamanio=1&pagina=1")
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].idCampania").value(antigua))
                .andExpect(jsonPath("$.total").value(2));
    }

    @Test
    void filtraPorCultivoParcelaYRangoDeFechas() throws Exception {
        String primera = crearFinalizadaReal("Primera", "1");
        String parcelaPrimera = idParcela;
        finalizar(primera).andExpect(status().isOk());
        idCultivo = crearCultivo("Trigo");
        String segunda = crearFinalizadaReal("Segunda", "1");
        finalizar(segunda).andExpect(status().isOk());
        fijarFinalizacion(primera, "2026-01-10T23:59:00Z");
        fijarFinalizacion(segunda, "2026-06-10T00:00:00Z");

        listar("?idCultivo=" + idCultivo)
                .andExpect(jsonPath("$.items[0].idCampania").value(segunda))
                .andExpect(jsonPath("$.total").value(1));
        listar("?idParcela=" + parcelaPrimera)
                .andExpect(jsonPath("$.items[0].idCampania").value(primera))
                .andExpect(jsonPath("$.total").value(1));
        listar("?fechaFinalizacionDesde=2026-06-10")
                .andExpect(jsonPath("$.items[0].idCampania").value(segunda))
                .andExpect(jsonPath("$.total").value(1));
        listar("?fechaFinalizacionHasta=2026-01-10")
                .andExpect(jsonPath("$.items[0].idCampania").value(primera))
                .andExpect(jsonPath("$.total").value(1));
        listar("?fechaFinalizacionDesde=2026-02-01&fechaFinalizacionHasta=2026-03-01")
                .andExpect(jsonPath("$.total").value(0));
    }

    @Test
    void paginaFueraDeRangoDevuelveListaVaciaConElTotalReal() throws Exception {
        String id = crearFinalizadaReal("Soya", "1");
        finalizar(id).andExpect(status().isOk());

        listar("?pagina=99")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", empty()))
                .andExpect(jsonPath("$.total").value(1));
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "?fechaFinalizacionDesde=2026-06-01&fechaFinalizacionHasta=2026-01-01",
            "?tamanio=501",
            "?tamanio=0",
            "?pagina=-1",
            "?idCultivo=no-es-uuid",
            "?fechaFinalizacionDesde=2026-06-01T00:00:00Z"
    })
    void parametrosInvalidosResponden400(String consulta) throws Exception {
        listar(consulta)
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"));
    }

    @Test
    void admiteHasta500PorPagina() throws Exception {
        listar("?tamanio=500").andExpect(status().isOk()).andExpect(jsonPath("$.tamanio").value(500));
    }

    @ParameterizedTest
    @ValueSource(strings = {"administrador", "gerencia", "tecnico_campo", "estado_campania"})
    void sinElRolDeLecturaResponde403(String rol) throws Exception {
        mockMvc.perform(get(RUTA_HISTORICOS).with(conRol(rol)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.codigo").value("SIN_PERMISO"));
    }

    @Test
    void laRutaDeHistoricosNoChocaConElDetalleDeCampania() throws Exception {
        mockMvc.perform(get(RUTA + "/" + UUID.randomUUID()).with(conRol("lectura_gestion")))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.codigo").value("CAMPANIA_NO_ENCONTRADA"));
        listar("").andExpect(status().isOk());
    }

    @Test
    void lasConsultasNoGeneranAuditoria() throws Exception {
        String id = crearFinalizadaReal("Soya", "1");
        finalizar(id).andExpect(status().isOk());
        Long antes = jdbc.queryForObject("SELECT count(*) FROM registro_auditoria", Long.class);

        listar("").andExpect(status().isOk());
        mockMvc.perform(get(RUTA + "/" + id + "/estado").with(conRol("estado_campania"))).andExpect(status().isOk());

        assertThat(jdbc.queryForObject("SELECT count(*) FROM registro_auditoria", Long.class)).isEqualTo(antes);
    }

    @Test
    void openApiDocumentaLasConsultas() throws Exception {
        String documento = mockMvc.perform(get("/v3/api-docs")).andReturn().getResponse().getContentAsString();
        JsonNode rutas = mapeador.readTree(documento).get("paths");

        assertThat(rutas.get(RUTA_HISTORICOS).get("get").get("responses").get("400").get("description").asText())
                .isEqualTo("DATOS_INVALIDOS");
        assertThat(rutas.get(RUTA + "/{id}/estado").get("get").get("responses").get("404").get("description").asText())
                .isEqualTo("CAMPANIA_NO_ENCONTRADA");
    }
}
