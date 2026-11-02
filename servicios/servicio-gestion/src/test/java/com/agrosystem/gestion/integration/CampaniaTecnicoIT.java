package com.agrosystem.gestion.integration;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

class CampaniaTecnicoIT extends CampaniaPruebaBase {

    private static final RequestPostProcessor TECNICO = conRol("tecnico_campo");

    @Test
    void listadoSoloIncluyeLasNoFinalizadas() throws Exception {
        String planificada = crearCampania("Planificada");
        crearFinalizada("Finalizada");

        mockMvc.perform(get(RUTA).with(TECNICO))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].id").value(planificada))
                .andExpect(jsonPath("$.items[0].resumen").doesNotExist())
                .andExpect(jsonPath("$.total").value(1));
    }

    @Test
    void filtrarPorFinalizadaDevuelveUnaListaVacia() throws Exception {
        crearFinalizada("Finalizada");

        mockMvc.perform(get(RUTA + "?estado=FINALIZADA").with(TECNICO))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(0)))
                .andExpect(jsonPath("$.total").value(0));
    }

    @Test
    void detalleDeNoFinalizadaNoIncluyeResumen() throws Exception {
        String id = crearCampania("Planificada");

        mockMvc.perform(get(RUTA + "/" + id).with(TECNICO))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.estado").value("PLANIFICADA"))
                .andExpect(jsonPath("$.nombre").value("Planificada"))
                .andExpect(jsonPath("$.resumen").doesNotExist());
    }

    @Test
    void detalleDeFinalizadaResponde403() throws Exception {
        String id = crearFinalizada("Finalizada");

        mockMvc.perform(get(RUTA + "/" + id).with(TECNICO))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.codigo").value("SIN_PERMISO"));
    }

    @Test
    void siTambienEsGerenciaRecibeLaVistaCompleta() throws Exception {
        String finalizada = crearFinalizada("Finalizada");
        RequestPostProcessor ambos = jwt().authorities(
                new SimpleGrantedAuthority("ROLE_tecnico_campo"),
                new SimpleGrantedAuthority("ROLE_gerencia"));

        mockMvc.perform(get(RUTA).with(ambos))
                .andExpect(jsonPath("$.total").value(1));
        mockMvc.perform(get(RUTA + "/" + finalizada).with(ambos))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.resumen.costoTotal").value("0.00"));
    }

    @Test
    void otrosRolesNoPuedenLeerCampanias() throws Exception {
        mockMvc.perform(get(RUTA).with(conRol("estado_campania")))
                .andExpect(status().isForbidden());
    }
}
