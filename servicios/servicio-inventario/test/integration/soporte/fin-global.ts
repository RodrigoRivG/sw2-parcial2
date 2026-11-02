export default async function finGlobal(): Promise<void> {
  await globalThis.contenedorMongoPruebas?.stop();
}
