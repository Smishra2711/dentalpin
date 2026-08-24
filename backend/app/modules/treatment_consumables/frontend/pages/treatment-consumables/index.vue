<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import {
  useTreatmentConsumables,
  type ConsumableLink,
  type LinkOptionTreatment,
  type LinkOptionItem
} from '../../composables/useTreatmentConsumables'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const linksApi = useTreatmentConsumables()

if (!can(PERMISSIONS.treatmentConsumables.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.treatmentConsumables.write))

// --- History table (server-side pagination) --------------------------------
const items = ref<ConsumableLink[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const PAGE_SIZE = 20
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

async function load() {
  loading.value = true
  try {
    const res = await linksApi.list({ page: page.value, page_size: PAGE_SIZE })
    items.value = res.data
    total.value = res.total
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

onMounted(load)

// --- Create modal: search-based pickers into both modules -------------------
const showModal = ref(false)
const saving = ref(false)
const searchQ = ref('')

const treatmentQuery = ref('')
const itemQuery = ref('')
const treatmentOptions = ref<LinkOptionTreatment[]>([])
const itemOptions = ref<LinkOptionItem[]>([])
const selectedTreatment = ref<LinkOptionTreatment | null>(null)
const selectedItem = ref<LinkOptionItem | null>(null)
const quantity = ref('1')
const note = ref('')
const formError = ref('')

let debounce: ReturnType<typeof setTimeout> | undefined
async function runPickers() {
  const res = await linksApi.linkOptions(searchQ.value || treatmentQuery.value || itemQuery.value || undefined)
  treatmentOptions.value = res.data.treatments
  itemOptions.value = res.data.items
}
watch([treatmentQuery, itemQuery], () => {
  clearTimeout(debounce)
  debounce = setTimeout(runPickers, 300)
})

function openAdd() {
  selectedTreatment.value = null
  selectedItem.value = null
  treatmentOptions.value = []
  itemOptions.value = []
  quantity.value = '1'
  note.value = ''
  formError.value = ''
  showModal.value = true
  runPickers()
}

async function submit() {
  formError.value = ''
  if (!selectedTreatment.value || !selectedItem.value) {
    formError.value = t('consumables.noMatches')
    return
  }
  saving.value = true
  try {
    await linksApi.create({
      catalog_item_id: selectedTreatment.value.id,
      inventory_item_id: selectedItem.value.id,
      quantity: quantity.value || '1',
      note: note.value || null
    })
    showModal.value = false
    await load()
  } catch {
    formError.value = t('consumables.noMatches')
  } finally {
    saving.value = false
  }
}

// --- Delete confirmation ------------------------------------------------------
const showDeleteConfirm = ref(false)
const linkToDelete = ref<ConsumableLink | null>(null)
const isDeleting = ref(false)

function confirmDelete(link: ConsumableLink) {
  linkToDelete.value = link
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!linkToDelete.value) return
  isDeleting.value = true
  try {
    await linksApi.remove(linkToDelete.value.id)
    showDeleteConfirm.value = false
    await load()
  } finally {
    isDeleting.value = false
  }
}

const columns = computed(() => [
  { accessorKey: 'treatment_name', header: t('consumables.treatment') },
  { accessorKey: 'item_name', header: t('consumables.item') },
  { accessorKey: 'quantity', header: t('consumables.quantity') },
  { accessorKey: 'note', header: t('consumables.note') },
  { id: 'actions' }
])
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div>
        <h1 class="text-h3 text-default">
          {{ t('consumables.title') }}
        </h1>
        <p class="text-ui text-subtle">
          {{ t('consumables.subtitle') }}
        </p>
      </div>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        @click="openAdd"
      >
        {{ t('consumables.add') }}
      </UButton>
    </div>

    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
    >
      <template #treatment_name-cell="{ row }">
        <span>{{ row.original.treatment_name }}</span>
        <span
          v-if="row.original.treatment_code"
          class="text-xs text-subtle ml-1"
        >({{ row.original.treatment_code }})</span>
      </template>
      <template #quantity-cell="{ row }">
        <UBadge
          variant="subtle"
          size="sm"
          class="tnum"
        >
          {{ row.original.quantity }}
        </UBadge>
      </template>
      <template #actions-cell="{ row }">
        <UButton
          v-if="canWrite"
          icon="i-lucide-unlink"
          variant="ghost"
          color="error"
          size="xs"
          :aria-label="t('consumables.delete')"
          @click="confirmDelete(row.original)"
        />
      </template>
    </UTable>

    <PaginationBar
      :page="page"
      :total-pages="totalPages"
      :total="total"
      :page-size="PAGE_SIZE"
      @update:page="onPage"
    />

    <!-- Create modal: search-based pickers into both modules -->
    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4 max-w-xl">
          <h2 class="text-h3 text-default">
            {{ t('consumables.add') }}
          </h2>
          <UInput
            v-model="searchQ"
            :placeholder="t('consumables.searchTreatments')"
            @update:model-value="treatmentQuery = $event; itemQuery = $event"
          />
          <div class="grid grid-cols-2 gap-2">
            <div class="space-y-1">
              <p class="text-xs text-subtle">
                {{ t('consumables.treatment') }}
              </p>
              <div class="max-h-40 overflow-auto rounded border border-default p-1 space-y-1">
                <button
                  v-for="tr in treatmentOptions"
                  :key="tr.id"
                  type="button"
                  class="w-full text-left px-2 py-1 rounded text-sm hover:bg-elevated"
                  :class="selectedTreatment?.id === tr.id ? 'bg-primary/10' : ''"
                  @click="selectedTreatment = tr"
                >
                  {{ tr.name }}
                </button>
                <p
                  v-if="!treatmentOptions.length"
                  class="text-sm text-subtle px-2"
                >
                  {{ t('consumables.noMatches') }}
                </p>
              </div>
            </div>
            <div class="space-y-1">
              <p class="text-xs text-subtle">
                {{ t('consumables.item') }}
              </p>
              <div class="max-h-40 overflow-auto rounded border border-default p-1 space-y-1">
                <button
                  v-for="it in itemOptions"
                  :key="it.id"
                  type="button"
                  class="w-full text-left px-2 py-1 rounded text-sm hover:bg-elevated"
                  :class="selectedItem?.id === it.id ? 'bg-primary/10' : ''"
                  @click="selectedItem = it"
                >
                  {{ it.name }}
                </button>
                <p
                  v-if="!itemOptions.length"
                  class="text-sm text-subtle px-2"
                >
                  {{ t('consumables.noMatches') }}
                </p>
              </div>
            </div>
          </div>
          <div class="flex gap-2">
            <UInput
              v-model="quantity"
              type="number"
              step="0.5"
              min="0.5"
              :placeholder="t('consumables.quantity')"
              class="w-32"
            />
            <UInput
              v-model="note"
              :placeholder="t('consumables.note')"
              class="flex-1"
            />
          </div>
          <div class="flex justify-end gap-2">
            <UButton
              variant="ghost"
              @click="showModal = false"
            >
              {{ t('actions.cancel') }}
            </UButton>
            <UButton
              :loading="saving"
              :disabled="!selectedTreatment || !selectedItem"
              @click="submit"
            >
              {{ t('consumables.add') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>

    <!-- Delete confirmation -->
    <UModal v-model:open="showDeleteConfirm">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('consumables.deleteTitle') }}
          </h2>
          <p class="text-ui text-subtle">
            {{ t('consumables.deleteMessage') }}
          </p>
          <div class="flex justify-end gap-2">
            <UButton
              variant="ghost"
              @click="showDeleteConfirm = false"
            >
              {{ t('actions.cancel') }}
            </UButton>
            <UButton
              color="error"
              :loading="isDeleting"
              @click="handleDelete"
            >
              {{ t('consumables.delete') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
