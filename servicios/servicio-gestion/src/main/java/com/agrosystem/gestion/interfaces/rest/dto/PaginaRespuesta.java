package com.agrosystem.gestion.interfaces.rest.dto;

import java.util.List;

public record PaginaRespuesta<T>(List<T> items, int pagina, int tamanio, long total) {
}
