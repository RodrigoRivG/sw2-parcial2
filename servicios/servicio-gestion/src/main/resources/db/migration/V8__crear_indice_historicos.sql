CREATE INDEX ix_campania_historicos ON campania (fecha_finalizacion DESC, id) WHERE estado = 'FINALIZADA';
