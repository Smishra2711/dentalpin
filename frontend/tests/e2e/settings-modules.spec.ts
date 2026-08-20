import { test, expect } from './_fixtures'

/**
 * Smoke for the admin module manager at /settings/modules.
 * - Admin can reach the page and see the module list.
 * - Non-admin cannot (page shows a forbidden message).
 */

test.describe('admin sees module manager', () => {
  test.use({ role: 'admin' })

  test('admin loads /settings/modules and sees module cards', async ({ loggedIn }) => {
    await loggedIn.goto('/settings/modules')

    // Page title (ES or EN, depending on user locale).
    await expect(
      loggedIn.getByRole('heading', { level: 1, name: /módulos|modules/i })
    ).toBeVisible()

    // At least one of the core modules must be listed — they are always
    // discovered, so this is a deterministic smoke check. Module cards
    // render after an async admin.refresh() fetch; the default 5s expect
    // timeout is tight now that the module list (and the app bundle) has
    // grown, so match the more generous timeout used elsewhere in this
    // suite for post-fetch assertions.
    await expect(
      loggedIn.getByRole('heading', { level: 3, name: /^patients$/ })
    ).toBeVisible({ timeout: 15_000 })
  })
})

test.describe('hygienist cannot reach module manager', () => {
  test.use({ role: 'hygienist' })

  test('hygienist sees forbidden message, no module cards', async ({ loggedIn }) => {
    await loggedIn.goto('/settings/modules')

    // No module cards rendered.
    await expect(
      loggedIn.getByRole('heading', { level: 3, name: /^patients$/ })
    ).toHaveCount(0)

    // The page renders a forbidden fallback.
    await expect(
      loggedIn.getByText(/acceso denegado|access denied/i)
    ).toBeVisible()
  })
})
