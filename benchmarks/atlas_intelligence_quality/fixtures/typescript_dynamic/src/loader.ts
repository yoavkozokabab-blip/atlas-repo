export async function loadPlugin(name: string) {
  return import(`./plugins/${name}.ts`);
}
