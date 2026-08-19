<script setup lang="ts">
// GST reconciliation report — explicitly a reconciliation aid, not a
// validated statutory GSTR-1 filing artifact (see the module CLAUDE.md).

definePageMeta({ layout: 'default' })

const { t } = useI18n()
const api = useApi()

interface Summary {
  cgst_total: string
  sgst_total: string
  igst_total: string
  invoice_count: number
  credit_note_count: number
  by_place_of_supply: Array<{ state_code: string | null, state_name: string | null, cgst: string, sgst: string, igst: string }>
}

interface TransactionRow {
  invoice_id: string
  gst_document_number: string | null
  issue_date: string | null
  recipient_gstin: string | null
  place_of_supply: string | null
  taxable_value: string
  cgst: string
  sgst: string
  igst: string
  status: string
  is_credit_note: boolean
}

const isLoading = ref(true)
const summary = ref<Summary | null>(null)
const transactions = ref<TransactionRow[]>([])

async function load() {
  isLoading.value = true
  const [summaryRes, txRes] = await Promise.all([
    api.get<{ data: Summary }>('/api/v1/india_gst/reports/summary'),
    api.get<{ data: TransactionRow[] }>('/api/v1/india_gst/reports/transactions')
  ])
  summary.value = summaryRes.data
  transactions.value = txRes.data
  isLoading.value = false
}

onMounted(load)

function exportCsv() {
  window.open('/api/v1/india_gst/reports/export', '_blank')
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-display text-default">
          {{ t('indiaGst.reports.title') }}
        </h1>
        <p class="text-subtle">
          {{ t('indiaGst.reports.description') }}
        </p>
      </div>
      <UButton
        icon="i-lucide-download"
        variant="outline"
        @click="exportCsv"
      >
        {{ t('indiaGst.reports.export') }}
      </UButton>
    </div>

    <USkeleton
      v-if="isLoading"
      class="h-96 w-full"
    />

    <template v-else-if="summary">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <UCard>
          <p class="text-caption text-subtle">
            CGST
          </p>
          <p class="text-xl font-semibold">
            {{ summary.cgst_total }}
          </p>
        </UCard>
        <UCard>
          <p class="text-caption text-subtle">
            SGST
          </p>
          <p class="text-xl font-semibold">
            {{ summary.sgst_total }}
          </p>
        </UCard>
        <UCard>
          <p class="text-caption text-subtle">
            IGST
          </p>
          <p class="text-xl font-semibold">
            {{ summary.igst_total }}
          </p>
        </UCard>
        <UCard>
          <p class="text-caption text-subtle">
            {{ t('indiaGst.reports.creditNotes') }}
          </p>
          <p class="text-xl font-semibold">
            {{ summary.credit_note_count }}
          </p>
        </UCard>
      </div>

      <UCard>
        <template #header>
          <h3 class="font-semibold text-default">
            {{ t('indiaGst.reports.byPlaceOfSupply') }}
          </h3>
        </template>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-subtle">
              <th class="py-1">
                {{ t('indiaGst.panel.placeOfSupply') }}
              </th>
              <th class="py-1 text-right">
                CGST
              </th>
              <th class="py-1 text-right">
                SGST
              </th>
              <th class="py-1 text-right">
                IGST
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in summary.by_place_of_supply"
              :key="row.state_code ?? 'unknown'"
              class="border-t border-default"
            >
              <td class="py-1">
                {{ row.state_name || row.state_code || '-' }}
              </td>
              <td class="py-1 text-right">
                {{ row.cgst }}
              </td>
              <td class="py-1 text-right">
                {{ row.sgst }}
              </td>
              <td class="py-1 text-right">
                {{ row.igst }}
              </td>
            </tr>
          </tbody>
        </table>
      </UCard>

      <UCard>
        <template #header>
          <h3 class="font-semibold text-default">
            {{ t('indiaGst.reports.transactions') }}
          </h3>
        </template>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-subtle">
              <th class="py-1">
                {{ t('indiaGst.panel.documentNumber') }}
              </th>
              <th class="py-1">
                {{ t('common.date') }}
              </th>
              <th class="py-1">
                {{ t('indiaGst.panel.placeOfSupply') }}
              </th>
              <th class="py-1 text-right">
                {{ t('indiaGst.reports.taxableValue') }}
              </th>
              <th class="py-1 text-right">
                CGST
              </th>
              <th class="py-1 text-right">
                SGST
              </th>
              <th class="py-1 text-right">
                IGST
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in transactions"
              :key="row.invoice_id"
              class="border-t border-default"
            >
              <td class="py-1">
                {{ row.gst_document_number || '-' }}
                <UBadge
                  v-if="row.is_credit_note"
                  size="xs"
                  color="neutral"
                  variant="subtle"
                >
                  CN
                </UBadge>
              </td>
              <td class="py-1">
                {{ row.issue_date || '-' }}
              </td>
              <td class="py-1">
                {{ row.place_of_supply || '-' }}
              </td>
              <td class="py-1 text-right">
                {{ row.taxable_value }}
              </td>
              <td class="py-1 text-right">
                {{ row.cgst }}
              </td>
              <td class="py-1 text-right">
                {{ row.sgst }}
              </td>
              <td class="py-1 text-right">
                {{ row.igst }}
              </td>
            </tr>
          </tbody>
        </table>
        <p
          v-if="transactions.length === 0"
          class="text-caption text-subtle text-center py-4"
        >
          {{ t('indiaGst.reports.empty') }}
        </p>
      </UCard>
    </template>
  </div>
</template>
