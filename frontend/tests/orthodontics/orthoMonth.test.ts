// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { orthoMonth } from '#module-layers/orthodontics/frontend/utils/orthoMonth'

describe('orthoMonth', () => {
  it('is month 1 on the start day and until the first monthiversary', () => {
    expect(orthoMonth('2026-01-15', new Date(2026, 0, 15))).toBe(1)
    expect(orthoMonth('2026-01-15', new Date(2026, 1, 14))).toBe(1)
  })

  it('advances on each monthiversary, across years', () => {
    expect(orthoMonth('2026-01-15', new Date(2026, 1, 15))).toBe(2)
    expect(orthoMonth('2025-11-30', new Date(2027, 0, 30))).toBe(15)
  })

  it('never goes below 1 for a future start date', () => {
    expect(orthoMonth('2026-12-01', new Date(2026, 0, 1))).toBe(1)
  })
})
