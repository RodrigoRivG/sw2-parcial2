package com.agrosystem.gestion.integration;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;

class FormatoEntradaIT extends PruebaIntegracionBase {

    private static final String RUTA = "/api/gestion/v1/prueba/";

    @Test
    void decimalComoTextoSeAcepta() throws Exception {
        mockMvc.perform(post(RUTA + "decimales").with(jwt()).contentType(MediaType.APPLICATION_JSON)
                        .content("{\"valor\": \"820.50\"}"))
                .andExpect(status().isOk());
    }

    @ParameterizedTest
    @ValueSource(strings = {"820.50", "820", "true", "\"abc\"", "\"1e5\"", "\"1,5\""})
    void decimalQueNoEsTextoDecimalResponde400(String valor) throws Exception {
        mockMvc.perform(post(RUTA + "decimales").with(jwt()).contentType(MediaType.APPLICATION_JSON)
                        .content("{\"valor\": " + valor + "}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"))
                .andExpect(jsonPath("$.detalles[0].campo").value("valor"));
    }

    @Test
    void paginacionUsaValoresPorDefecto() throws Exception {
        mockMvc.perform(get(RUTA + "pagina").with(jwt()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0]").value("a"))
                .andExpect(jsonPath("$.pagina").value(0))
                .andExpect(jsonPath("$.tamanio").value(20))
                .andExpect(jsonPath("$.total").value(1));
    }

    @ParameterizedTest
    @ValueSource(strings = {"pagina=-1", "tamanio=0", "tamanio=101", "tamanio=abc"})
    void paginacionFueraDeRangoResponde400(String parametro) throws Exception {
        mockMvc.perform(get(RUTA + "pagina?" + parametro).with(jwt()))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"));
    }
}
