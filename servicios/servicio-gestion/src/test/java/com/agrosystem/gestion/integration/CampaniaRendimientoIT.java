package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.agrosystem.gestion.infrastructure.persistence.entity.CampaniaEntidad;
import java.math.BigDecimal;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

class CampaniaRendimientoIT extends CampaniaPruebaBase {

    private static final Duration LIMITE = Duration.ofSeconds(3);

    @Test
    void listadoConFiltrosYDetalleRespondenEnMenosDe3SegundosCon5000Campanias() throws Exception {
        Instant ahora = Instant.now();
        UUID parcela = UUID.fromString(idParcela);
        UUID cultivo = UUID.fromString(idCultivo);
        LocalDate inicio = LocalDate.parse(INICIO);
        List<CampaniaEntidad> entidades = new ArrayList<>();
        for (int i = 0; i < 5000; i++) {
            CampaniaEntidad entidad = new CampaniaEntidad(UUID.randomUUID(), ahora);
            entidad.actualizar(
                    "Campania " + i,
                    parcela,
                    cultivo,
                    inicio.plusDays(i % 365),
                    inicio.plusDays(400),
                    new BigDecimal("25.5000"),
                    i % 2 == 0 ? "PLANIFICADA" : "FINALIZADA",
                    null,
                    null,
                    ahora);
            entidades.add(entidad);
        }
        campanias.saveAll(entidades);

        medir(get(RUTA + "?estado=FINALIZADA&idParcela=" + idParcela + "&idCultivo=" + idCultivo + "&tamanio=100"))
                .andExpect(jsonPath("$.total").value(2500));
        medir(get(RUTA + "/" + entidades.get(2500).getId()))
                .andExpect(jsonPath("$.nombre").value("Campania 2500"));
    }

    private ResultActions medir(MockHttpServletRequestBuilder solicitud) throws Exception {
        long inicio = System.nanoTime();
        ResultActions resultado = mockMvc.perform(solicitud.with(conRol("gerencia"))).andExpect(status().isOk());
        assertThat(Duration.ofNanos(System.nanoTime() - inicio)).isLessThan(LIMITE);
        return resultado;
    }
}
