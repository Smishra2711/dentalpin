<script setup lang="ts">
/**
 * Orthodontics sub-tab (patient clinical area, Diagnosis mode):
 * patient cases, new-case sheet, selected case sheet.
 */
import type { OrthoCase } from '../composables/useOrthodontics'
import { PERMISSIONS } from '~~/app/config/permissions'
import { toISODate } from '~~/app/utils/wallClock'
import OrthoCaseSheet from './OrthoCaseSheet.vue'

const props = defineProps<{ patientId: string }>()

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const { listCases, createCase } = useOrthodontics()
const { professionals, fetchProfessionals, getProfessionalFullName } = useProfessionals()

const canWrite = computed(() => can(PERMISSIONS.orthodontics.casesWrite))

const cases = ref<OrthoCase[]>([])
const selectedId = ref<string | undefined>()
const showNew = ref(false)
const isSaving = ref(false)
const appliance = ref('brackets_metal')
const startDate = ref(toISODate(new Date()))
const professionalId = ref<string | undefined>()
const months = ref<number | null>(null)
const notes = ref('')

const caseItems = computed(() => cases.value.map(c => ({
  label: `${t(`orthodontics.appliance.${c.appliance_type}`)} · ${c.start_date}`,
  value: c.id
})))
const professionalItems = computed(() => professionals.value.map(p => ({
  label: getProfessionalFullName(p),
  value: p.id
})))

async function refresh() {
  cases.value = await listCases({ patient_id: props.patientId })
  const first = cases.value[0]
  if (!selectedId.value && first) selectedId.value = first.id
}

async function openNew() {
  showNew.value = true
  if (professionals.value.length === 0) await fetchProfessionals()
}

async function save() {
  isSaving.value = true
  try {
    const created = await createCase({
      patient_id: props.patientId,
      appliance_type: appliance.value,
      start_date: startDate.value,
      professional_id: professionalId.value ?? null,
      estimated_months: months.value || null,
      diagnosis_notes: notes.value || null
    })
    showNew.value = false
    appliance.value = 'brackets_metal'
    startDate.value = toISODate(new Date())
    professionalId.value = undefined
    months.value = null
    notes.value = ''
    await refresh()
    selectedId.value = created.id
  } catch {
    toast.add({ title: t('orthodontics.errors.saveFailed'), color: 'error' })
  } finally {
    isSaving.value = false
  }
}

watch(() => props.patientId, () => {
  selectedId.value = undefined
  refresh().catch(() => toast.add({ title: t('orthodontics.errors.loadFailed'), color: 'error' }))
}, { immediate: true })
</script>

<template>
  <div>
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <USelect
        v-if="cases.length > 1"
        v-model="selectedId"
        :items="caseItems"
        value-key="value"
        label-key="label"
        class="min-w-56"
      />
      <UButton
        v-if="canWrite"
        size="sm"
        icon="i-lucide-plus"
        @click="openNew"
      >
        {{ t('orthodontics.case.new') }}
      </UButton>
    </div>

    <OrthoCaseSheet
      v-if="selectedId"
      :key="selectedId"
      :case-id="selectedId"
    />
    <p
      v-else
      class="text-sm text-gray-500"
    >
      {{ t('orthodontics.case.none') }}
    </p>

    <UModal
      v-model:open="showNew"
      :title="t('orthodontics.case.new')"
    >
      <template #body>
        <div class="space-y-3">
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ t('orthodontics.case.appliance') }}
            </div>
            <div class="flex flex-wrap gap-1">
              <UButton
                v-for="a in ['brackets_metal', 'brackets_esthetic', 'self_ligating', 'aligners', 'functional', 'retention']"
                :key="a"
                size="sm"
                :variant="appliance === a ? 'solid' : 'soft'"
                @click="appliance = a"
              >
                {{ t(`orthodontics.appliance.${a}`) }}
              </UButton>
            </div>
          </div>
          <UFormField :label="t('orthodontics.case.startDate')">
            <UInput
              v-model="startDate"
              type="date"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="t('orthodontics.case.professional')">
            <USelect
              v-model="professionalId"
              :items="professionalItems"
              value-key="value"
              label-key="label"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="t('orthodontics.case.estimatedMonths')">
            <UInput
              v-model.number="months"
              type="number"
              min="1"
              max="120"
              class="w-full"
            />
          </UFormField>
          <UTextarea
            v-model="notes"
            :placeholder="t('orthodontics.case.notes')"
            class="w-full"
          />
        </div>
      </template>
      <template #footer>
        <UButton
          :loading="isSaving"
          :disabled="!startDate"
          @click="save"
        >
          {{ t('orthodontics.case.create') }}
        </UButton>
      </template>
    </UModal>
  </div>
</template>
