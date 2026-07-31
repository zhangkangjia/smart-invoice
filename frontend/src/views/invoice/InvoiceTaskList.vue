<template>
  <div class="page-container">
    <PageHeader title="开票任务" :subtitle="currentBatchName ? `当前批次：${currentBatchName}` : '查看、重试或取消开票任务'">
      <template #actions>
        <el-button v-if="searchForm.batch_id" @click="clearBatchFilter">返回全部批次</el-button>
        <el-button type="primary" @click="router.push('/invoice-batches')">Excel订单导入</el-button>
      </template>
    </PageHeader>

    <el-alert v-if="searchForm.batch_id" type="info" :closable="false" show-icon class="batch-alert">
      正在查看指定批次下的任务，可返回全部批次任务。
    </el-alert>

    <SearchForm v-model="searchForm" @search="handleSearch" @reset="handleReset">
      <el-form-item label="企业">
        <el-select v-model="searchForm.enterprise_id" placeholder="全部" clearable filterable style="width: 200px">
          <el-option v-for="e in enterpriseOptions" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="opt in TASK_STATUS_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
        />
      </el-form-item>
    </SearchForm>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" stripe border empty-text="暂无开票任务">
        <el-table-column label="任务编号" width="120" show-overflow-tooltip>
          <template #default="{ row }"><span :title="row.id">{{ row.id?.slice(0, 8) || '-' }}</span></template>
        </el-table-column>
        <el-table-column prop="enterprise_name" label="销方企业" min-width="160" show-overflow-tooltip />
        <el-table-column prop="buyer_name" label="购方名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="价税合计" width="125" align="right"><template #default="{ row }">¥{{ formatAmount(row.total_with_tax) }}</template></el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <StatusTag :status="row.status" type="task" />
          </template>
        </el-table-column>
        <el-table-column label="重试次数" width="90" align="center">
          <template #default="{ row }">{{ row.retry_count || 0 }}/{{ row.max_retries || 3 }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleView(row)">查看</el-button>
            <el-button v-if="['failed', 'awaiting_manual'].includes(row.status)" link type="warning" size="small" @click="handleRetry(row)">重试</el-button>
            <el-button v-if="['pending_validation', 'validation_passed', 'pending_submit', 'queuing'].includes(row.status)" link type="danger" size="small" @click="handleCancel(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import SearchForm from '@/components/SearchForm.vue'
import { getInvoiceTasks, retryInvoiceTask, cancelInvoiceTask } from '@/api/invoice'
import { getEnterprises } from '@/api/enterprise'
import { TASK_STATUS_OPTIONS } from '@/utils/constants'
import { formatAmount, formatDate } from '@/utils/format'
import type { InvoiceTask, Enterprise } from '@/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const tableData = ref<InvoiceTask[]>([])
const enterpriseOptions = ref<Enterprise[]>([])
const dateRange = ref<[string, string] | null>(null)

const searchForm = reactive({
  enterprise_id: '',
  status: '' as string,
  batch_id: (route.query.batch_id as string) || ''
})
const currentBatchName = ref((route.query.batch_name as string) || '')

const pagination = reactive({ page: 1, page_size: 20, total: 0 })

watch(dateRange, (val) => {
  if (val) {
    ;(searchForm as any).start_date = val[0]
    ;(searchForm as any).end_date = val[1]
  } else {
    ;(searchForm as any).start_date = ''
    ;(searchForm as any).end_date = ''
  }
})

async function fetchEnterprises() {
  try {
    const res = await getEnterprises({ page: 1, page_size: 100 })
    enterpriseOptions.value = res.items
  } catch {
    // ignore
  }
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getInvoiceTasks({
      page: pagination.page,
      page_size: pagination.page_size,
      enterprise_id: searchForm.enterprise_id || undefined,
      status: searchForm.status || undefined,
      batch_id: searchForm.batch_id || undefined,
      start_date: (searchForm as any).start_date || undefined,
      end_date: (searchForm as any).end_date || undefined
    })
    tableData.value = res.items
    pagination.total = res.total
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  fetchData()
}

function handleReset() {
  pagination.page = 1
  dateRange.value = null
  fetchData()
}

function clearBatchFilter() {
  searchForm.batch_id = ''
  currentBatchName.value = ''
  router.replace({ path: '/invoice-tasks' })
  handleSearch()
}

function handleView(row: InvoiceTask) {
  router.push(`/invoice-tasks/${row.id}`)
}

async function handleRetry(row: InvoiceTask) {
  try {
    await ElMessageBox.confirm(`确定要重试任务「${row.id.substring(0, 8)}」吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await retryInvoiceTask(row.id)
    ElMessage.success('重试已提交')
    fetchData()
  } catch {
    // ignore
  }
}

async function handleCancel(row: InvoiceTask) {
  try {
    await ElMessageBox.confirm(`确定要取消任务「${row.id.substring(0, 8)}」吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await cancelInvoiceTask(row.id)
    ElMessage.success('任务已取消')
    fetchData()
  } catch {
    // ignore
  }
}

onMounted(() => {
  fetchEnterprises()
  fetchData()
})
</script>

<style scoped lang="scss">
.table-card {
  border-radius: 8px;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
