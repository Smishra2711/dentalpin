/**
 * Screen-pop (issue #64 §3, phase-1 polling flavour): while a user with
 * `telephony.calls.read` is logged in, poll the active-calls endpoint
 * and toast each new ringing call once — non-blocking, never navigates
 * on its own; the action button opens the patient record (or the
 * patient search pre-filtered by the caller's number).
 */
import { PERMISSIONS } from '~~/app/config/permissions'

const POLL_MS = 15000

export default defineNuxtPlugin((nuxtApp) => {
  const seen = new Set<string>()
  let timer: ReturnType<typeof setInterval> | undefined

  async function tick() {
    const { user } = useAuth()
    const { can } = usePermissions()
    if (!user.value || !can(PERMISSIONS.telephony.callsRead)) return

    const api = useApi()
    const toast = useToast()
    const t = (nuxtApp.$i18n as { t: (k: string) => string }).t
    try {
      const res = await api.get<{ data: Array<{
        id: string
        status: string
        from_number: string
        patient_id: string | null
        patient_name: string | null
      }> }>('/api/v1/telephony/calls/active', { errorToast: false })
      for (const call of res.data) {
        if (call.status !== 'ringing' || seen.has(call.id)) continue
        seen.add(call.id)
        toast.add({
          title: call.patient_name || t('telephony.calls.unknownCaller'),
          description: `${t('telephony.pop.incoming')} · ${call.from_number}`,
          icon: 'i-lucide-phone-incoming',
          color: 'warning',
          duration: 20000,
          actions: [{
            label: call.patient_id ? t('telephony.calls.openRecord') : t('telephony.calls.searchPatient'),
            onClick: () => {
              navigateTo(call.patient_id
                ? `/patients/${call.patient_id}`
                : `/patients?phone=${encodeURIComponent(call.from_number)}`)
            }
          }]
        })
      }
    } catch {
      // Background poll — a transient failure must stay invisible.
    }
  }

  if (import.meta.client) {
    timer = setInterval(tick, POLL_MS)
    nuxtApp.hook('app:unmount' as never, () => timer && clearInterval(timer))
  }
})
