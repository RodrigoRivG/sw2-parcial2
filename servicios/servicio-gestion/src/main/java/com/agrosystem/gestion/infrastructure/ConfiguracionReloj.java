package com.agrosystem.gestion.infrastructure;

import java.time.Clock;
import java.time.ZoneOffset;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ConfiguracionReloj {

    @Bean
    public Clock reloj() {
        return Clock.tickMillis(ZoneOffset.UTC);
    }
}
