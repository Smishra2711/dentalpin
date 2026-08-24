<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { useActivityJournal, type JournalEntry } from '../../composables/useActivityJournal'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const journalApi = useActivityJournal()

if (!can(PERMISSIONS.activityJournal.read)) {
  await navigateTo('/')
}

// --- List state (server-side pagination) ----------------------------------
const items = ref<JournalEntry[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const PAGE_SIZE = 20
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const filterType = ref<string | undefined>(undefined)
const filterDateFrom = ref<string>('')
const filterDateTo = ref<string>('')

async function load() {
  loading.value = true
  try {
    const res = await journalApi.list({
      event_type: filterType.value,
      date_from: filterDateFrom.value || undefined,
      date_to: filterDateTo.value || undefined,
      page: page.value,
      page_size: PAGE_SIZE
    })
    items.value = res.data
    total.value = res.total
    // A filter change can drop us past the last page.
    if (page.value > totalPages.value) {
      page.value = totalPages.value
      await load()
    }
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  load()
}

watch([filterType, filterDateFrom, filterDateTo], () => {
  page.value = 1
  load()
})

function fmtWhen(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  })
}

const columns = computed(() => [
  { accessorKey: 'occurred_at', header: t('journal.when') },
  { accessorKey: 'event_type', header: t('journal.event') },
  { accessorKey: 'actor_id', header: t('journal.actor') },
  { accessorKey: 'patient_id', header: t('journal.patient') },
  { accessorKey: 'source_table', header: t('journal.source') }
])

// --- Payload detail modal (read-only) --------------------------------------
const showDetail = ref(false)
const selected = ref<JournalEntry | null>(null)

const prettyPayload = computed(() =>
  selected.value ? JSON.stringify(selected.value.payload, null, 2) : ''
)

onMounted(load)
</script>

<template>
  <div class="space-y-4 p-4">
    <div>
      <h1 class="text-h3 text-default">
        {{ t('journal.title') }}
      </h1>
      <p class="text-ui text-subtle">
        {{ t('journal.subtitle') }}
      </p>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <UInput
        v-model="filterType"
        :placeholder="t('journal.filterByType')"
        class="max-w-xs"
      />
      <UInput
        v-model="filterDateFrom"
        type="date"
        :placeholder="t('journal.filterByDateFrom')"
      />
      <UInput
        v-model="filterDateTo"
        type="date"
        :placeholder="t('journal.filterByDateTo')"
      />
    </div>

    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
      @row-click="(row: any) => { selected = row.original; showDetail = true }"
    >
      <template #occurred_at-cell="{ row }">
        <span class="tnum">{{ fmtWhen(row.original.occurred_at) }}</span>
      </template>
      <template #event_type-cell="{ row }">
        <UBadge
          variant="subtle"
          size="sm"
        >
          {{ row.original.event_type }}
        </UBadge>
      </template>
      <template #actor_id-cell="{ row }">
        <span
          v-if="row.original.actor_id"
          class="tnum text-xs"
        >{{ row.original.actor_id.slice(0, 8) }}</span>
        <span
          v-else
          class="text-subtle"
        >{{ t('journal.unattributed') }}</span>
      </template>
      <template #patient_id-cell="{ row }">
        <span
          v-if="row.original.patient_id"
          class="tnum text-xs"
        >{{ row.original.patient_id.slice(0, 8) }}</span>
        <span
          v-else
          class="text-subtle"
        >{{ t('journal.unattributed') }}</span>
      </template>
    </UTable>

    <PaginationBar
      :page="page"
      :total-pages="totalPages"
      :total="total"
      :page-size="PAGE_SIZE"
      @update:page="onPage"
    />

    <!-- Payload detail -->
    <UModal v-model:open="showDetail">
      <template #content>
        <div class="p-4 space-y-4 max-w-2xl">
          <h2 class="text-h3 text-default">
            {{ t('journal.detailTitle') }}
          </h2>
          <pre class="text-xs bg-elevated p-3 rounded overflow-auto max-h-96">{{ prettyPayload }}</pre>
          <div class="flex justify-end">
            <UButton
              variant="ghost"
              @click="showDetail = false"
            >
              {{ t('actions.close') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
