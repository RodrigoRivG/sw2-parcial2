package com.agrosystem.gateway.web;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/** Escribe un {@link RespuestaError}; lo usan el manejador de errores y el punto de entrada 401. */
@Component
public class EscritorRespuestaError {

    private final ObjectMapper json;

    public EscritorRespuestaError(ObjectMapper json) {
        this.json = json;
    }

    public Mono<Void> escribir(ServerWebExchange exchange, HttpStatus estado, CodigoError error) {
        ServerHttpResponse respuesta = exchange.getResponse();
        String idCorrelacion = FiltroIdCorrelacion.de(exchange);
        respuesta.setStatusCode(estado);
        respuesta.getHeaders().setContentType(MediaType.APPLICATION_JSON);
        respuesta.getHeaders().set(FiltroIdCorrelacion.HEADER, idCorrelacion);
        byte[] cuerpo;
        try {
            cuerpo = json.writeValueAsBytes(RespuestaError.de(error.name(), error.mensaje(), idCorrelacion));
        } catch (JsonProcessingException e) {
            return Mono.error(e);
        }
        DataBuffer buffer = respuesta.bufferFactory().wrap(cuerpo);
        return respuesta.writeWith(Mono.just(buffer));
    }
}
