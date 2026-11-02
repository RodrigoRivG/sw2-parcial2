package com.agrosystem.gestion.integration;

import com.agrosystem.gestion.infrastructure.persistence.CultivoSpringData;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;

abstract class CultivoPruebaBase extends PruebaIntegracionBase {

    static final String RUTA = "/api/gestion/v1/cultivos";

    @Autowired
    protected CultivoSpringData cultivos;

    @BeforeEach
    void vaciarCultivos() {
        cultivos.deleteAll();
    }

    static String cuerpo(String nombre, String variedad) {
        String campoVariedad = variedad == null ? "" : "\"variedad\": \"" + variedad + "\", ";
        return "{\"nombre\": \"" + nombre + "\", " + campoVariedad + "\"unidadMedida\": \"KILOGRAMO\"}";
    }

    static String cuerpoConVersion(String nombre, String variedad, long version) {
        String campoVariedad = variedad == null ? "" : "\"variedad\": \"" + variedad + "\", ";
        return "{\"nombre\": \"" + nombre + "\", " + campoVariedad
                + "\"unidadMedida\": \"KILOGRAMO\", \"version\": " + version + "}";
    }
}
