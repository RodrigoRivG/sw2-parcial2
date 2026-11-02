package com.agrosystem.gestion.integration;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.test.web.servlet.ResultActions;

class EstadoCampaniaIT extends ProduccionPruebaBase {

    private ResultActions consultar(String id, String rol) throws Exception {
        return mockMvc.perform(get(RUTA + "/" + id + "/estado").with(conRol(rol)));
    }

    @Test
    void enCursoDevuelveElEstadoResumido() throws Exception {
        String id = crearCampaniaEnCurso("Soya");

        consultar(id, "estado_campania")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(id))
                .andExpect(jsonPath("$.idParcela").value(idParcela))
                .andExpect(jsonPath("$.idCultivo").value(idCultivo))
                .andExpect(jsonPath("$.estado").value("EN_CURSO"))
                .andExpect(jsonPath("$.fechaInicio").value(INICIO_PASADO))
                .andExpect(jsonPath("$.fechaFin").value(FIN_FUTURO))
                .andExpect(jsonPath("$.nombre").doesNotExist())
                .andExpect(jsonPath("$.resumen").doesNotExist());
    }

    @Test
    void cadaEstadoSeInformaSinDecidirPorElCliente() throws Exception {
        String planificada = crearCampaniaIniciable("Planificada");
        consultar(planificada, "estado_campania").andExpect(jsonPath("$.estado").value("PLANIFICADA"));

        String id = crearCampaniaEnCurso("Cerrada");
        registrarProduccion(id, cuerpoProduccion("100", HOY), "administrador").andExpect(status().isOk());
        finalizar(id).andExpect(status().isOk());

        consultar(id, "estado_campania")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.estado").value("FINALIZADA"));
    }

    @Test
    void idInexistenteResponde404() throws Exception {
        consultar(UUID.randomUUID().toString(), "estado_campania")
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.codigo").value("CAMPANIA_NO_ENCONTRADA"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"lectura_gestion", "administrador", "gerencia", "tecnico_campo"})
    void sinElRolDeEstadoResponde403(String rol) throws Exception {
        consultar(crearCampaniaIniciable("Soya"), rol)
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.codigo").value("SIN_PERMISO"));
    }
}
