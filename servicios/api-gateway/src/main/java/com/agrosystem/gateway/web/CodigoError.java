package com.agrosystem.gateway.web;

/** Errores propios del gateway (constitución §6 y spec-enrutamiento.md 1.4). */
public enum CodigoError {
    DATOS_INVALIDOS("La solicitud no es válida."),
    NO_AUTENTICADO("Debe iniciar sesión para continuar."),
    RUTA_NO_ENCONTRADA("La ruta solicitada no existe."),
    SERVICIO_NO_DISPONIBLE("El servicio solicitado no está disponible en este momento."),
    AUTENTICACION_NO_DISPONIBLE("No se pudo verificar la sesión. Intente nuevamente en unos minutos."),
    TIEMPO_AGOTADO("El servicio tardó demasiado en responder."),
    ERROR_INTERNO("Ocurrió un error inesperado.");

    private final String mensaje;

    CodigoError(String mensaje) {
        this.mensaje = mensaje;
    }

    public String mensaje() {
        return mensaje;
    }
}
