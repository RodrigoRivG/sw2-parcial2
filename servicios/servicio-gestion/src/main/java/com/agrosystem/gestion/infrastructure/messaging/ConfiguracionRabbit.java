package com.agrosystem.gestion.infrastructure.messaging;

import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ConfiguracionRabbit {

    @Bean
    public Queue colaComandos(
            @Value("${gestion.saga.cola-comandos}") String comandos,
            @Value("${gestion.saga.cola-errores}") String errores) {
        return QueueBuilder.durable(comandos)
                .deadLetterExchange("")
                .deadLetterRoutingKey(errores)
                .build();
    }

    @Bean
    public Queue colaErrores(@Value("${gestion.saga.cola-errores}") String errores) {
        return QueueBuilder.durable(errores).build();
    }

    /** La cola es de servicio-operaciones; se declara también para no perder respuestas si este arranca primero. */
    @Bean
    public Queue colaRespuestas(@Value("${gestion.saga.cola-respuestas}") String respuestas) {
        return QueueBuilder.durable(respuestas).build();
    }
}
