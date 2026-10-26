// Pure matching logic for "Quedamos".
// Kept completely independent from the UI so it can be tested in isolation.

export const DAYS = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
] as const

export const DAYS_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"] as const

export const START_HOUR = 8
export const END_HOUR = 22

// Hour blocks: 8:00-9:00 ... 21:00-22:00 (block identified by its start hour)
export const HOURS: number[] = Array.from(
  { length: END_HOUR - START_HOUR },
  (_, i) => START_HOUR + i,
)

// Availability states for a single cell.
export const UNAVAILABLE = 0
export const AVAILABLE = 1
export const HIGH_PREF = 2
export type AvailabilityState = 0 | 1 | 2

export interface Member {
  id: string
  name: string
  submitted: boolean
  availability: Record<string, AvailabilityState>
  /** Example member preloaded in demo mode (not a real person). */
  isDemo?: boolean
}

export interface Group {
  code: string
  name: string
  createdAt: number
  members: Member[]
}

export function blockKey(day: number, hour: number): string {
  return `${day}-${hour}`
}

export function formatHour(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`
}

export function formatBlockLabel(day: number, hour: number): string {
  return `${DAYS[day]} · ${formatHour(hour)} - ${formatHour(hour + 1)}`
}

export interface BlockScore {
  day: number
  hour: number
  key: string
  /** Members marked as available OR high preference. */
  availableCount: number
  /** Members marked specifically as high preference. */
  highPrefCount: number
  /** True when every member who responded is available in this block. */
  isFullMatch: boolean
}

/**
 * Score every hour block across the week.
 *
 * For each block we count how many members marked it as available or high
 * preference (both count as availability), and separately how many marked it
 * as high preference. Blocks with zero availability are omitted.
 *
 * Ordering: first by number of available members (desc), then, as a tie
 * breaker, by number of members that marked it as high preference (desc).
 */
export function computeBlockScores(members: Member[]): BlockScore[] {
  const responders = members.filter((m) => m.submitted)
  const total = responders.length

  const scores: BlockScore[] = []

  for (let day = 0; day < DAYS.length; day++) {
    for (const hour of HOURS) {
      const key = blockKey(day, hour)
      let availableCount = 0
      let highPrefCount = 0

      for (const member of responders) {
        const state = member.availability[key] ?? UNAVAILABLE
        if (state >= AVAILABLE) availableCount++
        if (state === HIGH_PREF) highPrefCount++
      }

      if (availableCount === 0) continue

      scores.push({
        day,
        hour,
        key,
        availableCount,
        highPrefCount,
        isFullMatch: total > 0 && availableCount === total,
      })
    }
  }

  scores.sort(
    (a, b) => b.availableCount - a.availableCount || b.highPrefCount - a.highPrefCount,
  )

  return scores
}

export interface Suggestions {
  /** Top blocks (already ordered), limited to `limit`. */
  top: BlockScore[]
  /** Blocks where 100% of responders coincide, ordered by high preference. */
  fullMatches: BlockScore[]
  /** Whether every responder coincides in at least one block. */
  hasFullMatch: boolean
  /** How many members have submitted their availability. */
  respondedCount: number
  /** Total members in the group. */
  totalCount: number
}

export function getSuggestions(members: Member[], limit = 5): Suggestions {
  const scores = computeBlockScores(members)
  const fullMatches = scores.filter((s) => s.isFullMatch)
  const respondedCount = members.filter((m) => m.submitted).length

  return {
    top: scores.slice(0, limit),
    fullMatches,
    hasFullMatch: fullMatches.length > 0,
    respondedCount,
    totalCount: members.length,
  }
}
