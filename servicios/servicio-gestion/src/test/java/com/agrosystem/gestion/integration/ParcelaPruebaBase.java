package com.agrosystem.gestion.integration;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;

import com.agrosystem.gestion.infrastructure.persistence.ParcelaSpringData;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

abstract class ParcelaPruebaBase extends PruebaIntegracionBase {

    static final String RUTA = "/api/gestion/v1/parcelas";

    @Autowired
    protected ParcelaSpringData parcelas;

    @BeforeEach
    void vaciarParcelas() {
        parcelas.deleteAll();
    }

    static RequestPostProcessor conRol(String rol) {
        return jwt().jwt(token -> token.subject("usuario-" + rol))
                .authorities(new SimpleGrantedAuthority("ROLE_" + rol));
    }

    static String cuerpo(String nombre, String superficie) {
        return "{\"nombre\": \"" + nombre + "\", \"superficieHectareas\": \"" + superficie + "\"}";
    }

    static String cuerpoConVersion(String nombre, String superficie, long version) {
        return "{\"nombre\": \"" + nombre + "\", \"superficieHectareas\": \"" + superficie
                + "\", \"version\": " + version + "}";
    }
}
