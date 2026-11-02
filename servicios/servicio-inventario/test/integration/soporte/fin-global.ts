export default async function finGlobal(): Promise<void> {
  await Promise.allSettled([
    globalThis.contenedorMongoPruebas?.stop(),
    globalThis.contenedorRabbitmqPruebas?.stop(),
  ]);
}
