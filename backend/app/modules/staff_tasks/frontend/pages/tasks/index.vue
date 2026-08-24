<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import {
  useStaffTasks,
  type StaffTask,
  type TaskPriority,
  type TaskStatus
} from '../../composables/useStaffTasks'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const tasksApi = useStaffTasks()

if (!can(PERMISSIONS.staffTasks.read)) await navigateTo('/')

const canWrite = computed(() => can(PERMISSIONS.staffTasks.write))

const STATUSES: TaskStatus[] = ['open', 'claimed', 'done', 'cancelled']
const PRIORITIES: TaskPriority[] = ['low', 'normal', 'high']

// --- List state (server-side pagination) ----------------------------------
const items = ref<StaffTask[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const PAGE_SIZE = 20
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const filterStatus = ref<TaskStatus | undefined>(undefined)

async function load() {
  loading.value = true
  try {
    const res = await tasksApi.list({
      task_status: filterStatus.value,
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

watch(filterStatus, () => {
  page.value = 1
  load()
})

type BadgeColor = 'error' | 'primary' | 'secondary' | 'success' | 'info' | 'warning' | 'neutral'

function statusColor(status: TaskStatus): BadgeColor {
  switch (status) {
    case 'open': return 'info'
    case 'claimed': return 'warning'
    case 'done': return 'success'
    default: return 'neutral'
  }
}

async function updateStatus(id: string, status: TaskStatus) {
  await tasksApi.update(id, { status })
  await load()
}

onMounted(load)

// --- Create modal ---
const showModal = ref(false)
const saving = ref(false)
const form = ref({
  title: '',
  details: '',
  priority: 'normal' as TaskPriority,
  due_date: ''
})

async function submit() {
  if (!form.value.title.trim()) return
  saving.value = true
  try {
    await tasksApi.create({
      title: form.value.title.trim(),
      details: form.value.details || undefined,
      priority: form.value.priority,
      due_date: form.value.due_date || undefined
    })
    showModal.value = false
    form.value = { title: '', details: '', priority: 'normal', due_date: '' }
    await load()
  } finally {
    saving.value = false
  }
}

// --- Delete confirmation (same pattern as the catalog settings page) ------
const showDeleteConfirm = ref(false)
const itemToDelete = ref<StaffTask | null>(null)
const isDeleting = ref(false)

function confirmDelete(task: StaffTask) {
  itemToDelete.value = task
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!itemToDelete.value) return
  isDeleting.value = true
  try {
    await tasksApi.remove(itemToDelete.value.id)
    showDeleteConfirm.value = false
    await load()
  } finally {
    isDeleting.value = false
  }
}

const columns = computed(() => [
  { accessorKey: 'title', header: t('staffTasks.title') },
  { accessorKey: 'priority', header: t('staffTasks.priority') },
  { accessorKey: 'due_date', header: t('staffTasks.dueDate') },
  { accessorKey: 'status', header: t('staffTasks.status') },
  { accessorKey: 'actions', header: '' }
])
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-h2 text-default">
        {{ t('staffTasks.title') }}
      </h1>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        @click="showModal = true"
      >
        {{ t('staffTasks.add') }}
      </UButton>
    </div>

    <USelect
      v-model="filterStatus"
      :items="STATUSES.map(value => ({ value, label: t(`staffTasks.statuses.${value}`) }))"
      :placeholder="t('staffTasks.filterByStatus')"
      class="max-w-xs"
    />

    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
    >
      <template #priority-cell="{ row }">
        <UBadge
          :color="row.original.priority === 'high' ? 'error' : row.original.priority === 'low' ? 'neutral' : 'info'"
          variant="subtle"
          size="xs"
        >
          {{ t(`staffTasks.priorities.${row.original.priority}`) }}
        </UBadge>
      </template>
      <template #status-cell="{ row }">
        <USelect
          v-if="canWrite"
          :model-value="row.original.status"
          :items="STATUSES.map(value => ({ value, label: t(`staffTasks.statuses.${value}`) }))"
          size="xs"
          @update:model-value="value => updateStatus(row.original.id, value as TaskStatus)"
        />
        <UBadge
          v-else
          :color="statusColor(row.original.status)"
          variant="subtle"
          size="xs"
        >
          {{ t(`staffTasks.statuses.${row.original.status}`) }}
        </UBadge>
      </template>
      <template #actions-cell="{ row }">
        <UButton
          v-if="canWrite"
          icon="i-lucide-trash-2"
          variant="ghost"
          color="error"
          size="xs"
          :aria-label="t('staffTasks.delete')"
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

    <!-- Create modal -->
    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('staffTasks.add') }}
          </h2>
          <UInput
            v-model="form.title"
            :placeholder="t('staffTasks.title')"
          />
          <UTextarea
            v-model="form.details"
            :placeholder="t('staffTasks.details')"
          />
          <USelect
            v-model="form.priority"
            :items="PRIORITIES.map(value => ({ value, label: t(`staffTasks.priorities.${value}`) }))"
            :placeholder="t('staffTasks.priority')"
          />
          <UInput
            v-model="form.due_date"
            type="date"
            :placeholder="t('staffTasks.dueDate')"
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
              :disabled="!form.title.trim()"
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
            {{ t('staffTasks.deleteTitle') }}
          </h2>
          <p class="text-ui text-subtle">
            {{ t('staffTasks.deleteMessage') }}
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
              {{ t('staffTasks.delete') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
