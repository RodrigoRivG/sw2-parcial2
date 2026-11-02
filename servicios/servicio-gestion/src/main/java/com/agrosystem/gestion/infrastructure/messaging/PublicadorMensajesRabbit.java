package com.agrosystem.gestion.infrastructure.messaging;

import com.agrosystem.gestion.application.port.PublicadorMensajes;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Clock;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageBuilder;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class PublicadorMensajesRabbit implements PublicadorMensajes {

    private static final int VERSION_SOBRE = 1;
    private static final String ORIGEN = "servicio-gestion";

    private final RabbitTemplate rabbit;
    private final ObjectMapper mapeador;
    private final Clock reloj;
    private final String colaRespuestas;
    private final String colaErrores;

    public PublicadorMensajesRabbit(
            RabbitTemplate rabbit,
            ObjectMapper mapeador,
            Clock reloj,
            @Value("${gestion.saga.cola-respuestas}") String colaRespuestas,
            @Value("${gestion.saga.cola-errores}") String colaErrores) {
        this.rabbit = rabbit;
        this.mapeador = mapeador;
        this.reloj = reloj;
        this.colaRespuestas = colaRespuestas;
        this.colaErrores = colaErrores;
    }

    @Override
    public void publicarRespuestaSaga(String tipo, String idCorrelacion, Map<String, Object> datos) {
        Map<String, Object> sobre = new LinkedHashMap<>();
        sobre.put("idMensaje", UUID.randomUUID());
        sobre.put("idCorrelacion", idCorrelacion);
        sobre.put("tipo", tipo);
        sobre.put("version", VERSION_SOBRE);
        sobre.put("fechaOcurrencia", reloj.instant().toString());
        sobre.put("origen", ORIGEN);
        sobre.put("datos", datos);
        try {
            rabbit.send("", colaRespuestas, mensaje(mapeador.writeValueAsBytes(sobre)));
        } catch (JsonProcessingException error) {
            throw new IllegalStateException("No se pudo serializar la respuesta " + tipo, error);
        }
    }

    @Override
    public void enviarAColaDeErrores(byte[] cuerpo) {
        rabbit.send("", colaErrores, mensaje(cuerpo));
    }

    private Message mensaje(byte[] cuerpo) {
        return MessageBuilder.withBody(cuerpo)
                .setContentType(MessageProperties.CONTENT_TYPE_JSON)
                .setDeliveryMode(MessageDeliveryMode.PERSISTENT)
                .build();
    }
}
