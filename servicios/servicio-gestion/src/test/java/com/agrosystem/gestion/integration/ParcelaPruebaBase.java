package com.agrosystem.gestion.integration;

import com.agrosystem.gestion.infrastructure.persistence.ParcelaSpringData;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;

abstract class ParcelaPruebaBase extends PruebaIntegracionBase {

    static final String RUTA = "/api/gestion/v1/parcelas";

    @Autowired
    protected ParcelaSpringData parcelas;

    @BeforeEach
    void vaciarParcelas() {
        parcelas.deleteAll();
    }

    static String cuerpo(String nombre, String superficie) {
        return "{\"nombre\": \"" + nombre + "\", \"superficieHectareas\": \"" + superficie + "\"}";
    }

    static String cuerpoConVersion(String nombre, String superficie, long version) {
        return "{\"nombre\": \"" + nombre + "\", \"superficieHectareas\": \"" + superficie
                + "\", \"version\": " + version + "}";
    }
}
