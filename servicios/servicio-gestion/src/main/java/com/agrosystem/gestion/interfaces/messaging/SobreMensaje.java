package com.agrosystem.gestion.interfaces.messaging;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.Optional;
import java.util.UUID;

/** Sobre común de mensajería. */
record SobreMensaje(
        UUID idMensaje,
        String idCorrelacion,
        String tipo,
        JsonNode version,
        JsonNode fechaOcurrencia,
        JsonNode origen,
        JsonNode datos) {

    /** Vacío si el mensaje no se puede interpretar: JSON inválido o sin idMensaje, idCorrelacion o tipo. */
    static Optional<SobreMensaje> interpretar(byte[] cuerpo, ObjectMapper mapeador) {
        try {
            JsonNode raiz = mapeador.readTree(cuerpo);
            if (raiz == null || !raiz.isObject()) {
                return Optional.empty();
            }
            String idCorrelacion = raiz.path("idCorrelacion").asText("");
            String tipo = raiz.path("tipo").asText("");
            if (idCorrelacion.isBlank() || tipo.isBlank()) {
                return Optional.empty();
            }
            return Optional.of(new SobreMensaje(
                    UUID.fromString(raiz.path("idMensaje").asText("")),
                    idCorrelacion,
                    tipo,
                    raiz.path("version"),
                    raiz.path("fechaOcurrencia"),
                    raiz.path("origen"),
                    raiz.path("datos")));
        } catch (IOException | IllegalArgumentException error) {
            return Optional.empty();
        }
    }
}
