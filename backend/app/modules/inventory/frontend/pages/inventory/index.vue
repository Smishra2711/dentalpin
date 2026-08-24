<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import {
  useInventory,
  type InventoryItem,
  type ItemCategory
} from '../../composables/useInventory'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const inventoryApi = useInventory()

if (!can(PERMISSIONS.inventory.read)) await navigateTo('/')

const canWrite = computed(() => can(PERMISSIONS.inventory.write))

const CATEGORIES: ItemCategory[] = ['consumables', 'equipment', 'office', 'other']
const categoryOptions = computed(() =>
  CATEGORIES.map(c => ({ value: c, label: t(`inventory.categories.${c}`) }))
)

// --- List state (server-side pagination) ----------------------------------
const items = ref<InventoryItem[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const PAGE_SIZE = 20
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const filterCategory = ref<ItemCategory | undefined>(undefined)
const lowStockOnly = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await inventoryApi.list({
      category: filterCategory.value,
      low_stock: lowStockOnly.value,
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

watch([filterCategory, lowStockOnly], () => {
  page.value = 1
  load()
})

onMounted(load)

// --- Create / edit modal ---------------------------------------------------
const showModal = ref(false)
const editing = ref<InventoryItem | null>(null)
const saving = ref(false)
const form = ref({
  name: '',
  category: 'other' as ItemCategory,
  unit: 'units',
  stock_quantity: 0,
  min_quantity: 0,
  notes: ''
})

function openCreate() {
  editing.value = null
  form.value = { name: '', category: 'other', unit: 'units', stock_quantity: 0, min_quantity: 0, notes: '' }
  showModal.value = true
}

function openEdit(item: InventoryItem) {
  editing.value = item
  form.value = {
    name: item.name,
    category: item.category,
    unit: item.unit,
    stock_quantity: Number(item.stock_quantity),
    min_quantity: Number(item.min_quantity),
    notes: item.notes ?? ''
  }
  showModal.value = true
}

async function submit() {
  if (!form.value.name.trim()) return
  saving.value = true
  try {
    if (editing.value) {
      await inventoryApi.update(editing.value.id, { ...form.value })
    } else {
      await inventoryApi.create({ ...form.value })
    }
    showModal.value = false
    await load()
  } finally {
    saving.value = false
  }
}

// --- Adjust (+/-) ----------------------------------------------------------
const adjustingId = ref<string | null>(null)

async function adjust(item: InventoryItem, delta: number) {
  adjustingId.value = item.id
  try {
    const res = await inventoryApi.adjust(item.id, delta)
    items.value = items.value.map(i => (i.id === res.data.id ? res.data : i))
  } finally {
    adjustingId.value = null
  }
}

// --- Delete confirmation ----------------------------------------------------
const showDeleteConfirm = ref(false)
const itemToDelete = ref<InventoryItem | null>(null)
const isDeleting = ref(false)

function confirmDelete(item: InventoryItem) {
  itemToDelete.value = item
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!itemToDelete.value) return
  isDeleting.value = true
  try {
    await inventoryApi.remove(itemToDelete.value.id)
    showDeleteConfirm.value = false
    await load()
  } finally {
    isDeleting.value = false
  }
}

const columns = computed(() => [
  { accessorKey: 'name', header: t('inventory.item') },
  { accessorKey: 'category', header: t('inventory.category') },
  { accessorKey: 'stock_quantity', header: t('inventory.stock') },
  { accessorKey: 'min_quantity', header: t('inventory.minimum') },
  { accessorKey: 'status', header: t('inventory.status') },
  { accessorKey: 'actions', header: '' }
])
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-h2 text-default">
        {{ t('inventory.title') }}
      </h1>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        @click="openCreate"
      >
        {{ t('inventory.add') }}
      </UButton>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <USelect
        v-model="filterCategory"
        :items="categoryOptions"
        :placeholder="t('inventory.filterByCategory')"
        class="max-w-xs"
      />
      <UCheckbox
        v-model="lowStockOnly"
        :label="t('inventory.lowStockOnly')"
      />
    </div>

    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
    >
      <template #stock_quantity-cell="{ row }">
        <div class="flex items-center gap-1">
          <UButton
            v-if="canWrite"
            icon="i-lucide-minus"
            size="xs"
            variant="ghost"
            :disabled="Number(row.original.stock_quantity) <= 0 || adjustingId === row.original.id"
            :aria-label="t('inventory.decrement')"
            @click="adjust(row.original, -1)"
          />
          <span class="tnum">{{ row.original.stock_quantity }} {{ row.original.unit }}</span>
          <UButton
            v-if="canWrite"
            icon="i-lucide-plus"
            size="xs"
            variant="ghost"
            :disabled="adjustingId === row.original.id"
            :aria-label="t('inventory.increment')"
            @click="adjust(row.original, 1)"
          />
        </div>
      </template>
      <template #min_quantity-cell="{ row }">
        <span class="tnum">{{ row.original.min_quantity }}</span>
      </template>
      <template #status-cell="{ row }">
        <UBadge
          :color="row.original.is_low_stock ? 'error' : 'success'"
          variant="subtle"
          size="xs"
        >
          {{ row.original.is_low_stock ? t('inventory.low') : t('inventory.ok') }}
        </UBadge>
      </template>
      <template #actions-cell="{ row }">
        <div class="flex items-center gap-1">
          <UButton
            v-if="canWrite"
            icon="i-lucide-pencil"
            variant="ghost"
            size="xs"
            :aria-label="t('inventory.edit')"
            @click="openEdit(row.original)"
          />
          <UButton
            v-if="canWrite"
            icon="i-lucide-trash-2"
            variant="ghost"
            color="error"
            size="xs"
            :aria-label="t('inventory.delete')"
            @click="confirmDelete(row.original)"
          />
        </div>
      </template>
    </UTable>

    <PaginationBar
      :page="page"
      :total-pages="totalPages"
      :total="total"
      :page-size="PAGE_SIZE"
      @update:page="onPage"
    />

    <!-- Create / edit modal -->
    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ editing ? t('inventory.edit') : t('inventory.add') }}
          </h2>
          <UInput
            v-model="form.name"
            :placeholder="t('inventory.item')"
          />
          <USelect
            v-model="form.category"
            :items="categoryOptions"
            :placeholder="t('inventory.category')"
          />
          <UInput
            v-model="form.unit"
            :placeholder="t('inventory.unit')"
          />
          <UInput
            v-model.number="form.stock_quantity"
            type="number"
            min="0"
            :placeholder="t('inventory.stock')"
          />
          <UInput
            v-model.number="form.min_quantity"
            type="number"
            min="0"
            :placeholder="t('inventory.minimum')"
          />
          <UTextarea
            v-model="form.notes"
            :placeholder="t('inventory.notes')"
          />
          <div class="flex justify-end gap-2">
            <UButton
              variant="ghost"
              @click="showModal = false"
            >
              {{ t('actions.cancel') }}
            </UButton>
            <UButton
              :loading="saving"
              :disabled="!form.name.trim()"
              @click="submit"
            >
              {{ t('actions.save') }}
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
            {{ t('inventory.deleteTitle') }}
          </h2>
          <p class="text-ui text-subtle">
            {{ t('inventory.deleteMessage') }}
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
              {{ t('inventory.delete') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
