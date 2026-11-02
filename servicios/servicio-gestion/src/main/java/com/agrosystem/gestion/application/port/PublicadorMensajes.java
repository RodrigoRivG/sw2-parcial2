package com.agrosystem.gestion.application.port;

import java.util.Map;

public interface PublicadorMensajes {

    /** Publica una respuesta de la Saga en la cola del coordinador, con el sobre común. */
    void publicarRespuestaSaga(String tipo, String idCorrelacion, Map<String, Object> datos);

    /** Envía a la Dead Letter Queue un mensaje que no se puede interpretar. */
    void enviarAColaDeErrores(byte[] cuerpo);
}
