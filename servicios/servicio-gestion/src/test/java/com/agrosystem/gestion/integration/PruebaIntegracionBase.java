package com.agrosystem.gestion.integration;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.RabbitMQContainer;

/** Una sola pareja de contenedores por ejecución, reutilizada por todos los tests *IT. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
public abstract class PruebaIntegracionBase {

    @ServiceConnection
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:17-alpine");

    @ServiceConnection
    static final RabbitMQContainer RABBIT = new RabbitMQContainer("rabbitmq:4-management-alpine");

    static {
        POSTGRES.start();
        RABBIT.start();
    }

    @Autowired
    protected MockMvc mockMvc;

    protected static RequestPostProcessor conRol(String rol) {
        return jwt().jwt(token -> token.subject("usuario-" + rol))
                .authorities(new SimpleGrantedAuthority("ROLE_" + rol));
    }
}
