// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

// Module-layer frontend code (backend/app/modules/*/frontend) lives outside
// this directory, so `eslint .` never saw it — files there were reported as
// "outside of base path" and silently skipped, in CI too. The
// `module_layers` symlink (mirroring the docker-compose mount of the same
// name) brings the layers inside the base path; `npm run lint` passes it
// explicitly because ESLint does not traverse symlinked directories on its
// own. Running from the repo root with --config is not an option: the
// Nuxt-generated config only resolves relative to this directory.
export default withNuxt(
  {
    // Mirror `nuxt/disables/routes`: routed components are allowed
    // single-word names (new.vue, index.vue, [id].vue).
    name: 'dentalpin/module-layers/routes',
    files: ['module_layers/*/frontend/{pages,layouts}/**/*.{js,ts,jsx,tsx,vue}'],
    rules: {
      'vue/multi-word-component-names': 'off'
    }
  },
  {
    // #522: `new Date(y, m, d).toISOString().slice(0, 10)` renders a *local*
    // midnight in UTC, which is the previous day for every zone ahead of it —
    // wrong at midday in Madrid, Rome, Warsaw, Budapest and Kolkata, not just
    // near midnight. That shipped in 32 places before anyone noticed, and a
    // one-off sweep goes stale the moment a module lands (orthodontics
    // arrived with #505 carrying two fresh copies). `toISODate(d)` reads the
    // Y-M-D fields off the Date; `clinicToday(tz)` is the one for "today".
    name: 'dentalpin/dates/no-utc-day-slicing',
    files: ['app/**/*.{js,ts,vue}', 'module_layers/*/frontend/**/*.{js,ts,vue}'],
    rules: {
      'no-restricted-syntax': ['error',
        {
          selector:
            'CallExpression[callee.object.callee.property.name="toISOString"][callee.property.name="slice"]',
          message:
            'Use toISODate(d) from ~~/app/utils/wallClock (or clinicToday(tz) for today). '
            + 'toISOString() renders the instant in UTC, so a local midnight comes back as the previous day (#522).'
        },
        {
          selector:
            'CallExpression[callee.object.callee.property.name="toISOString"][callee.property.name="split"]',
          message:
            'Use toISODate(d) from ~~/app/utils/wallClock (or clinicToday(tz) for today). '
            + 'toISOString() renders the instant in UTC, so a local midnight comes back as the previous day (#522).'
        }
      ]
    }
  },
  {
    // Python bytecode caches under backend/app/modules would otherwise be
    // traversed when `module_layers` is passed as a lint target.
    ignores: ['module_layers/**/__pycache__/**', 'module_layers/**/migrations/**']
  }
)
