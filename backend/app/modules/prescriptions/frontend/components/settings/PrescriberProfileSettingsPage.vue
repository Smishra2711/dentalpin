<script setup lang="ts">
/**
 * Prescriber identity (Settings → Clinical). Own license number used
 * for the snapshot taken at issue time; per-user defaults.
 */
import { PERMISSIONS } from '~~/app/config/permissions'

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const { getPrescriberProfile, upsertPrescriberProfile } = usePrescriptions()

const canWrite = computed(() => can(PERMISSIONS.prescriptions.write))
const licenseNumber = ref('')
const isLoading = ref(false)
const country = useClinicCountry()

/**
 * Professional terminology follows the clinic country when it has its
 * own term (MX: cédula profesional); otherwise the UI locale default.
 * Frontend mirror of the backend hook `label_overrides` seam
 * (prescriptions/hooks.py): a country module's backend hook governs
 * PDFs, this governs the settings caption. Extend the map (never the
 * i18n keys) when another country needs its own term.
 */
const LICENSE_LABEL_BY_COUNTRY: Record<string, string> = {
  MX: 'Cédula profesional'
}
const licenseLabel = computed(
  () => LICENSE_LABEL_BY_COUNTRY[(country.value ?? '').toUpperCase()] ?? t('prescriptions.licenseLabel')
)

async function refresh() {
  isLoading.value = true
  try {
    const profile = await getPrescriberProfile()
    licenseNumber.value = profile?.license_number || ''
  } finally {
    isLoading.value = false
  }
}

async function save() {
  try {
    await upsertPrescriberProfile(licenseNumber.value.trim() || null)
    toast.add({ title: t('common.success'), color: 'success' })
    await refresh()
  } catch { /* useApi already toasted the failure */ }
}

onMounted(refresh)
</script>

<template>
  <div class="space-y-2">
    <USkeleton
      v-if="isLoading"
      class="h-10"
    />
    <template v-else>
      <UFormField :label="licenseLabel">
        <UInput
          v-model="licenseNumber"
          :disabled="!canWrite"
        />
      </UFormField>
      <UButton
        v-if="canWrite"
        size="xs"
        @click="save"
      >
        {{ t('prescriptions.save') }}
      </UButton>
    </template>
  </div>
</template>
