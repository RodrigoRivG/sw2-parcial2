package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.sql.Date;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.ResultActions;

class IntegracionRendimientoIT extends ProduccionPruebaBase {

    private static final int CAMPANIAS = 5000;

    private List<UUID> sembrarFinalizadas() {
        Timestamp ahora = Timestamp.from(Instant.now());
        UUID parcela = UUID.fromString(idParcela);
        UUID cultivo = UUID.fromString(idCultivo);
        Date inicio = Date.valueOf(LocalDate.parse(INICIO_PASADO));
        Date fin = Date.valueOf(LocalDate.parse(FIN_FUTURO));
        Date cosecha = Date.valueOf(HOY);
        List<UUID> ids = new ArrayList<>();
        List<Object[]> filasCampania = new ArrayList<>();
        List<Object[]> filasProduccion = new ArrayList<>();
        List<Object[]> filasCosto = new ArrayList<>();
        for (int i = 0; i < CAMPANIAS; i++) {
            UUID id = UUID.randomUUID();
            ids.add(id);
            filasCampania.add(new Object[] {id, "Campania " + i, parcela, cultivo, inicio, fin, ahora, ahora, ahora, ahora});
            filasProduccion.add(new Object[] {id, cosecha, ahora});
            for (int costo = 0; costo < 4; costo++) {
                filasCosto.add(new Object[] {UUID.randomUUID(), id, cosecha, ahora});
            }
        }
        jdbc.batchUpdate("INSERT INTO campania (id, nombre, id_parcela, id_cultivo, fecha_inicio, fecha_fin, superficie_hectareas, "
                + "estado, fecha_inicio_ejecucion, fecha_finalizacion, version, fecha_creacion, fecha_actualizacion) "
                + "VALUES (?, ?, ?, ?, ?, ?, 25.5, 'FINALIZADA', ?, ?, 0, ?, ?)", filasCampania);
        jdbc.batchUpdate("INSERT INTO produccion_campania (id_campania, cantidad, unidad, fecha_cosecha, fecha_registro, usuario_registro) "
                + "VALUES (?, 76500, 'KILOGRAMO', ?, ?, 'prueba')", filasProduccion);
        jdbc.batchUpdate("INSERT INTO costo_campania (id, id_campania, categoria, monto, fecha, descripcion, origen, fecha_registro) "
                + "VALUES (?, ?, 'OTRO', 9562.50, ?, 'Costo', 'MANUAL', ?)", filasCosto);
        return ids;
    }

    @Test
    void estadoEHistoricosCumplenSusTiemposCon5000CampaniasFinalizadas() throws Exception {
        List<UUID> ids = sembrarFinalizadas();

        long inicio = System.nanoTime();
        ResultActions resultado = mockMvc.perform(get(RUTA + "/historicos?tamanio=500").with(conRol("lectura_gestion")));
        Duration historicos = Duration.ofNanos(System.nanoTime() - inicio);
        resultado
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(500))
                .andExpect(jsonPath("$.total").value(CAMPANIAS))
                .andExpect(jsonPath("$.items[0].costoTotal").value("38250.00"))
                .andExpect(jsonPath("$.items[0].rendimientoPorHectarea").value("3000.00"));
        assertThat(historicos).isLessThan(Duration.ofSeconds(3));

        List<Duration> tiempos = new ArrayList<>();
        for (int i = 0; i < 100; i++) {
            long comienzo = System.nanoTime();
            ResultActions estado = mockMvc.perform(get(RUTA + "/" + ids.get(i) + "/estado").with(conRol("estado_campania")));
            tiempos.add(Duration.ofNanos(System.nanoTime() - comienzo));
            estado.andExpect(status().isOk()).andExpect(jsonPath("$.estado").value("FINALIZADA"));
        }
        Collections.sort(tiempos);
        assertThat(tiempos.get(99)).isLessThan(Duration.ofSeconds(3));
        assertThat(tiempos.get(94)).as("p95 de la consulta de estado").isLessThan(Duration.ofMillis(300));
    }
}
