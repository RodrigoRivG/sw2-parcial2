package com.agrosystem.gestion.integration;

import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

class ManejoErroresIT extends PruebaIntegracionBase {

    private static final String RUTA = "/api/gestion/v1/prueba/";

    @Test
    void validacionResponde400ConDetallePorCampo() throws Exception {
        mockMvc.perform(post(RUTA + "decimales").with(jwt())
                        .contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"))
                .andExpect(jsonPath("$.detalles[0].campo").value("valor"))
                .andExpect(jsonPath("$.idCorrelacion").isNotEmpty());
    }

    @Test
    void jsonMalFormadoResponde400() throws Exception {
        mockMvc.perform(post(RUTA + "decimales").with(jwt())
                        .contentType(MediaType.APPLICATION_JSON).content("{ no es json"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"));
    }

    @Test
    void rutaInexistenteResponde404() throws Exception {
        mockMvc.perform(get("/api/gestion/v1/no-existe").with(jwt()))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.codigo").value("RECURSO_NO_ENCONTRADO"));
    }

    @Test
    void metodoNoPermitidoResponde405() throws Exception {
        mockMvc.perform(delete(RUTA + "autenticado").with(jwt()))
                .andExpect(status().isMethodNotAllowed())
                .andExpect(jsonPath("$.codigo").value("METODO_NO_PERMITIDO"));
    }

    @Test
    void fechaConHoraResponde400() throws Exception {
        mockMvc.perform(post(RUTA + "fechas").with(jwt()).contentType(MediaType.APPLICATION_JSON)
                        .content("{\"fecha\": \"2026-11-15T00:00:00Z\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"))
                .andExpect(jsonPath("$.detalles[0].campo").value("fecha"));
    }

    @Test
    void fechaSinHoraSeAcepta() throws Exception {
        mockMvc.perform(post(RUTA + "fechas").with(jwt()).contentType(MediaType.APPLICATION_JSON)
                        .content("{\"fecha\": \"2026-11-15\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.fecha").value("2026-11-15"));
    }

    @Test
    void excepcionesDeDominioUsanSuCodigoYEstado() throws Exception {
        mockMvc.perform(get(RUTA + "dominio/NO_ENCONTRADO").with(jwt()))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.codigo").value("CODIGO_PRUEBA"));
        mockMvc.perform(get(RUTA + "dominio/CONFLICTO").with(jwt()))
                .andExpect(status().isConflict());
        mockMvc.perform(get(RUTA + "dominio/REGLA_NEGOCIO").with(jwt()))
                .andExpect(status().isUnprocessableEntity());
    }

    @Test
    void parametroDeRutaInvalidoResponde400() throws Exception {
        mockMvc.perform(get(RUTA + "dominio/INEXISTENTE").with(jwt()))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"));
    }

    @Test
    void conflictoDeVersionResponde409() throws Exception {
        mockMvc.perform(get(RUTA + "concurrencia").with(jwt()))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.codigo").value("CONFLICTO_CONCURRENCIA"));
    }

    @Test
    void errorInesperadoResponde500SinExponerDetalles() throws Exception {
        mockMvc.perform(get(RUTA + "fallo").with(jwt()))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.codigo").value("ERROR_INTERNO"))
                .andExpect(content().string(not(containsString("secreto"))));
    }
}
