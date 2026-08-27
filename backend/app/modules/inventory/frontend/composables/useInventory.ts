export type ItemCategory = 'consumables' | 'equipment' | 'office' | 'other'

export interface InventoryItem {
  id: string
  clinic_id: string
  name: string
  category: ItemCategory
  unit: string
  stock_quantity: string
  min_quantity: string
  is_low_stock: boolean
  notes?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface InventoryItemCreatePayload {
  name: string
  category: ItemCategory
  unit: string
  stock_quantity: number
  min_quantity: number
  notes?: string | null
}

export interface InventoryItemUpdatePayload {
  name?: string
  category?: ItemCategory
  unit?: string
  stock_quantity?: number
  min_quantity?: number
  notes?: string | null
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface InventoryListFilters {
  category?: ItemCategory
  low_stock?: boolean
  page?: number
  page_size?: number
}

export function useInventory() {
  const api = useApi()

  // Every caller (pages/inventory/index.vue) catches and toasts via its
  // own `notifyError` — suppress useApi's auto-toast to stay single-toast.
  async function list(filters: InventoryListFilters = {}): Promise<ApiPaged<InventoryItem>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '' || v === false) continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/inventory/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<InventoryItem>>(url, { errorToast: false })
  }

  async function create(payload: InventoryItemCreatePayload): Promise<ApiOk<InventoryItem>> {
    return await api.post<ApiOk<InventoryItem>>('/api/v1/inventory/', payload, { errorToast: false })
  }

  async function update(id: string, payload: InventoryItemUpdatePayload): Promise<ApiOk<InventoryItem>> {
    return await api.patch<ApiOk<InventoryItem>>(`/api/v1/inventory/${id}`, payload, { errorToast: false })
  }

  async function adjust(id: string, delta: number): Promise<ApiOk<InventoryItem>> {
    // 409 (stock would go negative) is an expected branch the page toasts.
    return await api.post<ApiOk<InventoryItem>>(`/api/v1/inventory/${id}/adjust`, { delta }, { errorToast: false })
  }

  async function remove(id: string): Promise<void> {
    await api.del(`/api/v1/inventory/${id}`, { errorToast: false })
  }

  return { list, create, update, adjust, remove }
}
