package com.agrosystem.gestion.domain.shared;

import java.util.List;

public record Pagina<T>(List<T> items, long total) {
}
