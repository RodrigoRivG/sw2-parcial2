package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageBuilder;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitAdmin;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;

abstract class SagaPruebaBase extends ProduccionPruebaBase {

    private static final long ESPERA_RESPUESTA_MS = 20_000;

    @Autowired
    protected RabbitTemplate rabbit;

    @Autowired
    protected RabbitAdmin administrador;

    @Value("${gestion.saga.cola-comandos}")
    protected String colaComandos;

    @Value("${gestion.saga.cola-errores}")
    protected String colaErrores;

    @Value("${gestion.saga.cola-respuestas}")
    protected String colaRespuestas;

    @BeforeEach
    void vaciarColasYSagas() {
        administrador.purgeQueue(colaRespuestas);
        administrador.purgeQueue(colaErrores);
        jdbc.update("DELETE FROM mensaje_procesado");
        jdbc.update("DELETE FROM saga_procesada");
    }

    protected void enviarCrudo(String cuerpo) {
        Message mensaje = MessageBuilder.withBody(cuerpo.getBytes(StandardCharsets.UTF_8))
                .setContentType(MessageProperties.CONTENT_TYPE_JSON)
                .build();
        rabbit.send("", colaComandos, mensaje);
    }

    protected String sobre(UUID idMensaje, String correlacion, String tipo, int version, String datos) {
        return "{\"idMensaje\": \"" + idMensaje + "\", \"idCorrelacion\": \"" + correlacion + "\", \"tipo\": \"" + tipo
                + "\", \"version\": " + version + ", \"fechaOcurrencia\": \"" + Instant.now()
                + "\", \"origen\": \"servicio-operaciones\", \"datos\": " + datos + "}";
    }

    protected String datosRegistro(UUID saga, UUID labor, String campania, String monto) {
        return "{\"idSaga\": \"" + saga + "\", \"idLabor\": \"" + labor + "\", \"idCampania\": \"" + campania
                + "\", \"monto\": \"" + monto + "\", \"categoria\": \"INSUMO\"}";
    }

    protected String datosAnulacion(UUID saga, UUID labor, String campania) {
        return "{\"idSaga\": \"" + saga + "\", \"idLabor\": \"" + labor + "\", \"idCampania\": \"" + campania + "\"}";
    }

    protected void enviarRegistro(UUID saga, UUID labor, String campania, String monto) {
        enviarCrudo(sobre(UUID.randomUUID(), saga.toString(), "RegistrarCostoCampania", 1,
                datosRegistro(saga, labor, campania, monto)));
    }

    protected void enviarAnulacion(UUID saga, UUID labor, String campania) {
        enviarCrudo(sobre(UUID.randomUUID(), saga.toString(), "AnularCostoCampania", 1,
                datosAnulacion(saga, labor, campania)));
    }

    protected JsonNode recibirRespuesta() throws Exception {
        Message mensaje = rabbit.receive(colaRespuestas, ESPERA_RESPUESTA_MS);
        assertThat(mensaje).as("respuesta en la cola del coordinador").isNotNull();
        return mapeador.readTree(mensaje.getBody());
    }

    protected Message recibirError(long esperaMs) {
        return rabbit.receive(colaErrores, esperaMs);
    }

    protected BigDecimal costoTotalDe(String campania) {
        BigDecimal total = jdbc.queryForObject(
                "SELECT coalesce(sum(monto), 0) FROM costo_campania WHERE id_campania = ? AND NOT anulado",
                BigDecimal.class,
                UUID.fromString(campania));
        return total;
    }

    protected long costosDe(String campania) {
        return jdbc.queryForObject(
                "SELECT count(*) FROM costo_campania WHERE id_campania = ?", Long.class, UUID.fromString(campania));
    }

    protected String resultadoDe(UUID saga) {
        return jdbc.queryForObject("SELECT resultado FROM saga_procesada WHERE id_saga = ?", String.class, saga);
    }
}
