package com.agrosystem.gestion.integration;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

class PermisosIntegracionIT extends ProduccionPruebaBase {

    private static final String PARCELAS = "/api/gestion/v1/parcelas";
    private static final String CULTIVOS = "/api/gestion/v1/cultivos";

    private List<MockHttpServletRequestBuilder> escrituras() {
        String id = UUID.randomUUID().toString();
        return List.of(
                post(PARCELAS),
                put(PARCELAS + "/" + id),
                post(CULTIVOS),
                put(CULTIVOS + "/" + id),
                post(RUTA),
                put(RUTA + "/" + id),
                put(RUTA + "/" + id + "/estado"),
                post(RUTA + "/" + id + "/costos"),
                put(RUTA + "/" + id + "/costos/" + id),
                delete(RUTA + "/" + id + "/costos/" + id),
                put(RUTA + "/" + id + "/produccion"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"lectura_gestion", "estado_campania"})
    void ningunaCuentaDeServicioPuedeEscribir(String rol) throws Exception {
        for (MockHttpServletRequestBuilder escritura : escrituras()) {
            mockMvc.perform(escritura.with(conRol(rol)).contentType(MediaType.APPLICATION_JSON).content("{}"))
                    .andExpect(status().isForbidden())
                    .andExpect(jsonPath("$.codigo").value("SIN_PERMISO"));
        }
    }

    @Test
    void graphqlConAmbosRolesLeeComoGerenciaPeroNoEscribe() throws Exception {
        RequestPostProcessor graphql = SecurityMockMvcRequestPostProcessors.jwt().authorities(
                new SimpleGrantedAuthority("ROLE_lectura_gestion"),
                new SimpleGrantedAuthority("ROLE_estado_campania"));
        String campania = crearCampaniaEnCurso("Soya");

        for (String ruta : List.of(
                PARCELAS,
                PARCELAS + "/" + idParcela,
                CULTIVOS,
                CULTIVOS + "/" + idCultivo,
                RUTA,
                RUTA + "/" + campania,
                RUTA + "/" + campania + "/estado",
                RUTA + "/" + campania + "/costos",
                RUTA + "/" + campania + "/indicadores",
                RUTA + "/historicos")) {
            mockMvc.perform(get(ruta).with(graphql)).andExpect(status().isOk());
        }
        for (MockHttpServletRequestBuilder escritura : escrituras()) {
            mockMvc.perform(escritura.with(graphql).contentType(MediaType.APPLICATION_JSON).content("{}"))
                    .andExpect(status().isForbidden());
        }
    }

    @Test
    void sinTokenLasConsultasRespondenNoAutenticado() throws Exception {
        for (String ruta : List.of(RUTA + "/historicos", RUTA + "/" + UUID.randomUUID() + "/estado")) {
            mockMvc.perform(get(ruta))
                    .andExpect(status().isUnauthorized())
                    .andExpect(jsonPath("$.codigo").value("NO_AUTENTICADO"));
        }
    }
}
