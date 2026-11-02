package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;

import com.agrosystem.gestion.application.campaign.ComandoRegistrarCosto;
import com.agrosystem.gestion.application.campaign.RegistrarCostoSagaCasoUso;
import com.agrosystem.gestion.application.campaign.RespuestaSaga;
import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

class IdempotenciaSagaIT extends SagaPruebaBase {

    @Autowired
    private RegistrarCostoSagaCasoUso registrar;

    private final UUID saga = UUID.randomUUID();
    private final UUID labor = UUID.randomUUID();

    @Test
    void mismoIdSagaConOtroIdMensajeNoDuplicaYRepiteLosDatos() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        enviarRegistro(saga, labor, campania, "820.50");
        JsonNode primera = recibirRespuesta();

        enviarRegistro(saga, labor, campania, "820.50");
        JsonNode segunda = recibirRespuesta();

        assertThat(segunda.get("datos")).isEqualTo(primera.get("datos"));
        assertThat(segunda.get("tipo")).isEqualTo(primera.get("tipo"));
        assertThat(costosDe(campania)).isEqualTo(1);
    }

    @Test
    void mismoIdMensajeNoDuplicaNiFalla() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        UUID mensaje = UUID.randomUUID();
        String cuerpo = sobre(mensaje, saga.toString(), "RegistrarCostoCampania", 1,
                datosRegistro(saga, labor, campania, "10"));

        enviarCrudo(cuerpo);
        JsonNode primera = recibirRespuesta();
        enviarCrudo(cuerpo);
        JsonNode segunda = recibirRespuesta();

        assertThat(segunda.get("datos")).isEqualTo(primera.get("datos"));
        assertThat(costosDe(campania)).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT count(*) FROM mensaje_procesado WHERE id_mensaje = ?", Long.class, mensaje))
                .isEqualTo(1);
    }

    @Test
    void rechazoRepetidoSeMantieneAunqueCambieLaCampania() throws Exception {
        String campania = crearFinalizada("Cerrada");
        enviarRegistro(saga, labor, campania, "10");
        JsonNode primera = recibirRespuesta();
        jdbc.update("UPDATE campania SET estado = 'PLANIFICADA' WHERE id = ?", UUID.fromString(campania));

        enviarRegistro(saga, labor, campania, "10");
        JsonNode segunda = recibirRespuesta();

        assertThat(segunda.get("tipo").asText()).isEqualTo("CostoCampaniaRechazado");
        assertThat(segunda.get("datos")).isEqualTo(primera.get("datos"));
        assertThat(costosDe(campania)).isZero();
    }

    @Test
    void repetidoConOtroMontoRespondeElResultadoOriginal() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        enviarRegistro(saga, labor, campania, "10.00");
        recibirRespuesta();

        enviarRegistro(saga, labor, campania, "99.00");
        JsonNode respuesta = recibirRespuesta();

        assertThat(respuesta.get("datos").get("monto").asText()).isEqualTo("10.00");
        assertThat(costoTotalDe(campania)).isEqualByComparingTo("10");
    }

    @Test
    void cienEntregasEnSerieDejanUnSoloCosto() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        for (int i = 0; i < 100; i++) {
            enviarRegistro(saga, labor, campania, "1.00");
        }
        for (int i = 0; i < 100; i++) {
            assertThat(recibirRespuesta().get("tipo").asText()).isEqualTo("CostoCampaniaRegistrado");
        }

        assertThat(costosDe(campania)).isEqualTo(1);
    }

    @Test
    void cienEntregasEnParaleloDejanUnSoloCostoYLaMismaRespuesta() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        Callable<RespuestaSaga> entrega = () -> registrar.ejecutar(new ComandoRegistrarCosto(
                UUID.randomUUID(), saga, labor, UUID.fromString(campania), new BigDecimal("1.00"),
                LocalDate.parse(HOY), "servicio-operaciones"));

        List<RespuestaSaga> respuestas = new ArrayList<>();
        try (ExecutorService hilos = Executors.newFixedThreadPool(8)) {
            List<Future<RespuestaSaga>> futuros = new ArrayList<>();
            for (int i = 0; i < 100; i++) {
                futuros.add(hilos.submit(entrega));
            }
            for (Future<RespuestaSaga> futuro : futuros) {
                respuestas.add(futuro.get());
            }
        }

        assertThat(costosDe(campania)).isEqualTo(1);
        assertThat(new HashSet<>(respuestas)).hasSize(1);
    }
}
