export interface JournalEntry {
  id: string
  clinic_id: string
  event_type: string
  actor_id?: string | null
  patient_id?: string | null
  source_table: string
  source_entity_id?: string | null
  payload: Record<string, unknown>
  occurred_at: string
}

interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface JournalListFilters {
  event_type?: string
  patient_id?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export function useActivityJournal() {
  const api = useApi()

  async function list(filters: JournalListFilters = {}): Promise<ApiPaged<JournalEntry>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/activity_journal/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<JournalEntry>>(url)
  }

  async function get(id: string): Promise<JournalEntry> {
    const res = await api.get<{ data: JournalEntry }>(`/api/v1/activity_journal/${id}`)
    return res.data
  }

  return { list, get }
}
