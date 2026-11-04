package com.agrosystem.gateway.web;

import org.springframework.core.annotation.Order;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.ReactiveSecurityContextHolder;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

/**
 * Corre después de la cadena de seguridad (orden -100) y deja el {@code sub} del token en un atributo
 * del exchange para {@link RegistroAcceso}, que corre antes de la seguridad y no ve la autenticación.
 */
@Component
@Order(0)
public class FiltroSujeto implements WebFilter {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain cadena) {
        return ReactiveSecurityContextHolder.getContext()
                .map(SecurityContext::getAuthentication)
                .filter(Authentication::isAuthenticated)
                .doOnNext(autenticacion -> exchange.getAttributes().put(RegistroAcceso.ATRIBUTO_SUB, autenticacion.getName()))
                .then(cadena.filter(exchange));
    }
}
