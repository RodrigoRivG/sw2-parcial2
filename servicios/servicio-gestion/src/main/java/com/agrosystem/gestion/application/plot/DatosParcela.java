package com.agrosystem.gestion.application.plot;

import java.math.BigDecimal;

public record DatosParcela(String nombre, BigDecimal superficieHectareas, String ubicacion, String descripcion) {
}
