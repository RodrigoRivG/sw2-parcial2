package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.agrosystem.gestion.infrastructure.persistence.entity.ParcelaEntidad;
import java.math.BigDecimal;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

class ParcelaRendimientoIT extends ParcelaPruebaBase {

    private static final Duration LIMITE = Duration.ofSeconds(3);

    @Test
    void listadoYDetalleRespondenEnMenosDe3SegundosCon1000Parcelas() throws Exception {
        Instant ahora = Instant.now();
        List<ParcelaEntidad> entidades = new ArrayList<>();
        for (int i = 0; i < 1000; i++) {
            ParcelaEntidad entidad = new ParcelaEntidad(UUID.randomUUID(), ahora);
            entidad.actualizar("Lote %04d".formatted(i), new BigDecimal("10.0000"), null, null, ahora);
            entidades.add(entidad);
        }
        parcelas.saveAll(entidades);

        medir(get(RUTA + "?tamanio=100&nombre=lote"))
                .andExpect(jsonPath("$.total").value(1000));
        medir(get(RUTA + "/" + entidades.get(500).getId()))
                .andExpect(jsonPath("$.nombre").value("Lote 0500"));

        parcelas.deleteAll();
    }

    private ResultActions medir(MockHttpServletRequestBuilder solicitud)
            throws Exception {
        long inicio = System.nanoTime();
        ResultActions resultado = mockMvc.perform(solicitud.with(conRol("gerencia"))).andExpect(status().isOk());
        assertThat(Duration.ofNanos(System.nanoTime() - inicio)).isLessThan(LIMITE);
        return resultado;
    }
}
