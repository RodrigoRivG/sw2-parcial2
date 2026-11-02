CREATE TABLE cultivo (
    id                   UUID PRIMARY KEY,
    nombre               VARCHAR(100) NOT NULL,
    variedad             VARCHAR(100),
    unidad_medida        VARCHAR(20)  NOT NULL CHECK (unidad_medida IN ('KILOGRAMO')),
    descripcion          VARCHAR(500),
    version              BIGINT       NOT NULL,
    fecha_creacion       TIMESTAMPTZ  NOT NULL,
    fecha_actualizacion  TIMESTAMPTZ  NOT NULL
);
CREATE UNIQUE INDEX ux_cultivo_nombre_variedad
    ON cultivo (lower(nombre), lower(coalesce(variedad, '')));
