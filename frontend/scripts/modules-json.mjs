// Write `modules.json` listing every module layer under <layers-root>.
//
//   node scripts/modules-json.mjs <layers-root>
//
// The backend regenerates this file at runtime as modules are installed;
// build/CI contexts have no backend, so they bake every layer instead:
//   Dockerfile.prod  → /module_layers            (COPY of backend/app/modules)
//   CI e2e           → $GITHUB_WORKSPACE/backend/app/modules
//   CI typecheck     → ./module_layers           (symlink, same trick as ESLint)
import { existsSync, readdirSync, writeFileSync } from 'node:fs'

const root = process.argv[2]
if (!root) {
  console.error('usage: node scripts/modules-json.mjs <layers-root>')
  process.exit(1)
}
const names = readdirSync(root)
  .filter(name => existsSync(`${root}/${name}/frontend/nuxt.config.ts`))
  .sort()
const modules = names.map(name => ({ name, path: `${root}/${name}/frontend` }))
writeFileSync(
  'modules.json',
  JSON.stringify({ layers: modules.map(m => m.path), modules, version: 1 }, null, 2) + '\n'
)
console.log('modules.json:', names.join(', '))
