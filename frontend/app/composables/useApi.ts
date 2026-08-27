import type { ApiResponse, PaginatedResponse } from '~/types'
import { errorDetail } from '~/utils/error'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface UseApiOptions {
  method?: HttpMethod
  // Accept any plain object so callers can pass a typed domain payload
  // (e.g. ``BudgetCreate``) without an ``as unknown as Record<…>`` cast.
  // ``$fetch`` serializes via JSON.stringify, which handles any object.
  body?: object | null
  headers?: Record<string, string>
  skipAuth?: boolean
  // Query-string params appended to the path. Undefined/null values are
  // skipped. Provided because $fetch's own ``query`` was not wired here,
  // so callers that passed ``{ params: … }`` had it silently dropped
  // (e.g. the Veri*Factu queue tabs all rendered the same list).
  query?: Record<string, string | number | boolean | undefined | null>
  // Optional AbortSignal so callers can cancel in-flight requests
  // (debounced lookups, component unmount, etc.).
  signal?: AbortSignal
  // 400/409/422 toast the backend's own message by default before
  // rethrowing (#101 — an uncaught rethrow used to be a silent
  // failure). Callers that surface the error themselves (their own
  // toast, inline form error, modal copy) pass ``errorToast: false``
  // to keep single-toast behaviour. 404 never auto-toasts: it is
  // routinely semantic ("not signed", probe-style reads) and its
  // handling belongs to the caller.
  errorToast?: boolean
}

function _withQuery(path: string, query?: UseApiOptions['query']): string {
  if (!query) return path
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null) qs.set(k, String(v))
  }
  const s = qs.toString()
  if (!s) return path
  return path.includes('?') ? `${path}&${s}` : `${path}?${s}`
}

export function useApi() {
  const config = useRuntimeConfig()
  const auth = useAuth()
  const { t } = useI18n()
  const toast = useToast()

  // Use different API URL for server (Docker internal) vs client (browser)
  const apiBaseUrl = computed(() =>
    import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
  )

  async function $api<T>(
    path: string,
    options: UseApiOptions = {}
  ): Promise<T> {
    const { skipAuth, method, body, headers: optionHeaders, signal, query, errorToast = true } = options

    const headers: Record<string, string> = {
      ...(optionHeaders || {})
    }

    // Add auth header if authenticated and not skipping auth
    if (!skipAuth && auth.accessToken.value) {
      headers.Authorization = `Bearer ${auth.accessToken.value}`
    }

    const url = _withQuery(path, query)

    try {
      return await $fetch<T>(url, {
        baseURL: apiBaseUrl.value,
        timeout: 10000, // 10 seconds
        method,
        body,
        headers,
        signal
      })
    } catch (error: unknown) {
      const fetchError = error as { name?: string, statusCode?: number, data?: { message?: string } }

      // Caller-initiated cancellation: don't toast, just rethrow so the
      // caller can no-op. AbortController is used by orchestrators
      // (e.g. dashboard) to cancel stale parallel fetches.
      if (fetchError.name === 'AbortError' || signal?.aborted) {
        throw error
      }

      // Handle specific error codes
      if (fetchError.statusCode === 401) {
        // Try to refresh token
        const refreshed = await auth.refresh()
        if (refreshed) {
          // Retry the request with new token
          headers.Authorization = `Bearer ${auth.accessToken.value}`
          return await $fetch<T>(url, {
            baseURL: apiBaseUrl.value,
            method,
            body,
            headers
          })
        }
        // Redirect to login
        await auth.logout()
        throw error
      }

      if (fetchError.statusCode === 403) {
        toast.add({
          title: t('common.error'),
          description: t('common.forbidden', 'Acceso denegado'),
          color: 'error'
        })
        throw error
      }

      if (fetchError.statusCode === 404) {
        // Semantic more often than exceptional (probe-reads, "not
        // signed", lookups) — never auto-toast; the caller owns it.
        throw error
      }

      if (
        errorToast
        && (fetchError.statusCode === 400
          || fetchError.statusCode === 409
          || fetchError.statusCode === 422)
      ) {
        // Surface the backend's own message so a rethrow nobody catches
        // is no longer silent (#101). Callers that present the error
        // themselves suppress this with ``errorToast: false``.
        toast.add({
          title: t('common.error'),
          description: errorDetail(error) ?? t('common.serverError'),
          color: 'error'
        })
        throw error
      }

      if (
        fetchError.statusCode === 400
        || fetchError.statusCode === 409
        || fetchError.statusCode === 422
      ) {
        throw error
      }

      if (fetchError.statusCode && fetchError.statusCode >= 500) {
        toast.add({
          title: t('common.error'),
          description: t('common.serverError'),
          color: 'error'
        })
        throw error
      }

      // Network error
      if (!fetchError.statusCode) {
        toast.add({
          title: t('common.error'),
          description: t('common.networkError'),
          color: 'error'
        })
      }

      throw error
    }
  }

  // Convenience methods
  async function get<T>(path: string, options: Omit<UseApiOptions, 'method' | 'body'> = {}): Promise<T> {
    return $api<T>(path, { ...options, method: 'GET' })
  }

  async function post<T>(path: string, body?: object | null, options: Omit<UseApiOptions, 'method' | 'body'> = {}): Promise<T> {
    return $api<T>(path, { ...options, method: 'POST', body })
  }

  async function put<T>(path: string, body?: object | null, options: Omit<UseApiOptions, 'method' | 'body'> = {}): Promise<T> {
    return $api<T>(path, { ...options, method: 'PUT', body })
  }

  async function patch<T>(path: string, body?: object | null, options: Omit<UseApiOptions, 'method' | 'body'> = {}): Promise<T> {
    return $api<T>(path, { ...options, method: 'PATCH', body })
  }

  async function del<T>(path: string, options: Omit<UseApiOptions, 'method' | 'body'> = {}): Promise<T> {
    return $api<T>(path, { ...options, method: 'DELETE' })
  }

  return {
    $api,
    get,
    post,
    put,
    patch,
    del
  }
}

// Type helpers for API responses
export type { ApiResponse, PaginatedResponse }
