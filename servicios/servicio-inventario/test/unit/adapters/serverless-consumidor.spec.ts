import { AmqpConnectionManager } from 'amqp-connection-manager';
import { ComandosSagaConsumidor } from '../../../src/adapters/inbound/messaging/comandos-saga.consumidor';
import { Configuracion, leerConfiguracion } from '../../../src/config/validacion-entorno';

const entorno = {
  PORT: '3000',
  MONGODB_URI: 'mongodb://ficticio/inventario',
  RABBITMQ_URL: 'amqp://ficticio',
  KEYCLOAK_ISSUER: 'https://auth.ficticio/realms/agro',
  KEYCLOAK_JWKS_URI: 'https://auth.ficticio/certs',
  KEYCLOAK_AUDIENCE: 'servicio-inventario',
};

function crear(configuracion?: Configuracion) {
  const canal = { consume: jest.fn().mockResolvedValue(undefined) };
  const conexion = {
    createChannel: jest.fn().mockReturnValue(canal),
  } as unknown as AmqpConnectionManager;
  const consumidor = new ComandosSagaConsumidor(
    conexion,
    null!,
    null!,
    null!,
    null!,
    [],
    configuracion,
  );
  return { consumidor, canal };
}

test('la configuración local conserva el consumidor activo por defecto', () => {
  expect(leerConfiguracion(entorno).rabbitmqConsumidorActivo).toBe(true);
  const { consumidor, canal } = crear();
  consumidor.onApplicationBootstrap();
  expect(canal.consume).toHaveBeenCalledTimes(1);
});

test('la copia HTTP desactivada no consume mensajes de la Saga', () => {
  const config = leerConfiguracion({ ...entorno, RABBITMQ_CONSUMIDOR_ACTIVO: 'false' });
  const { consumidor, canal } = crear(config);
  consumidor.onApplicationBootstrap();
  expect(canal.consume).not.toHaveBeenCalled();
});

test('la copia de trabajo activa se suscribe a la cola', () => {
  const { consumidor, canal } = crear(leerConfiguracion(entorno));
  consumidor.onApplicationBootstrap();
  expect(canal.consume).toHaveBeenCalledTimes(1);
});

test('una bandera inválida falla antes de arrancar', () => {
  expect(() => leerConfiguracion({ ...entorno, RABBITMQ_CONSUMIDOR_ACTIVO: 'no' })).toThrow(
    'RABBITMQ_CONSUMIDOR_ACTIVO',
  );
});
