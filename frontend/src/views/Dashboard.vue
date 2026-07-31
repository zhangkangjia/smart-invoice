<template>
  <div class="page-container">
    <PageHeader title="开票工作台" subtitle="从订单导入开始，集中跟踪批次和待处理事项">
      <template #actions>
        <el-button @click="router.push('/exceptions')">处理异常</el-button>
        <el-button type="primary" @click="router.push('/invoice-batches')"><el-icon><Upload /></el-icon>Excel订单导入</el-button>
      </template>
    </PageHeader>

    <el-row :gutter="16" class="metric-row">
      <el-col v-for="card in cards" :key="card.label" :span="6">
        <div class="metric-card" :class="card.tone" @click="card.path && router.push(card.path)">
          <span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.note }}</small>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="15">
        <el-card shadow="never" class="content-card">
          <template #header><div class="card-header"><span>最近导入批次</span><el-link type="primary" :underline="false" @click="router.push('/invoice-batches')">进入开票任务台</el-link></div></template>
          <el-table v-loading="batchLoading" :data="batches" stripe empty-text="暂无导入批次，点击右上角开始导入">
            <el-table-column prop="file_name" label="导入文件" min-width="220"><template #default="{ row }">{{ row.file_name || '未命名导入' }}</template></el-table-column>
            <el-table-column prop="task_count" label="任务数" width="90" align="center" />
            <el-table-column prop="success_count" label="成功" width="90" align="center"><template #default="{ row }"><span class="success-text">{{ row.success_count || 0 }}</span></template></el-table-column>
            <el-table-column prop="exception_count" label="异常" width="90" align="center"><template #default="{ row }"><span class="danger-text">{{ row.exception_count || 0 }}</span></template></el-table-column>
            <el-table-column label="导入时间" width="165"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
            <el-table-column label="操作" width="90"><template #default="{ row }"><el-button link type="primary" @click="router.push({ path: '/invoice-tasks', query: { batch_id: row.id, batch_name: row.file_name || '' } })">查看任务</el-button></template></el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="9">
        <el-card shadow="never" class="content-card">
          <template #header><div class="card-header"><span>待处理事项</span><el-link type="primary" :underline="false" @click="router.push('/work-items')">查看全部</el-link></div></template>
          <el-table v-loading="workLoading" :data="workItems" size="small" empty-text="暂无待办事项">
            <el-table-column prop="work_type" label="类型" min-width="110" />
            <el-table-column label="优先级" width="80"><template #default="{ row }"><StatusTag :status="row.priority" type="priority" /></template></el-table-column>
            <el-table-column label="操作" width="72"><template #default="{ row }"><el-button link type="primary" @click="router.push('/work-items')">处理</el-button></template></el-table-column>
          </el-table>
          <el-button class="exception-button" type="danger" plain @click="router.push('/exceptions')">查看系统异常（{{ dashboard.open_exceptions || 0 }}）</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Upload } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { getDashboardStats } from '@/api/statistics'
import { getInvoiceBatches } from '@/api/invoice'
import { getWorkItems } from '@/api/work_item'
import { formatDateTime } from '@/utils/format'

const router = useRouter()
const dashboard = ref<any>({})
const batches = ref<any[]>([])
const workItems = ref<any[]>([])
const batchLoading = ref(false)
const workLoading = ref(false)

const cards = computed(() => {
  const status = dashboard.value.task_status_breakdown || {}
  return [
    { label: '启用企业', value: dashboard.value.enterprise_count || 0, note: '可自动开票的销方', tone: 'blue', path: '/enterprises' },
    { label: '全部开票任务', value: dashboard.value.invoice_task_count || 0, note: '累计任务量', tone: 'neutral', path: '/invoice-tasks' },
    { label: '处理中', value: (status.queuing || 0) + (status.submitting || 0) + (status.confirming || 0), note: '正在等待或提交通道', tone: 'orange', path: '/invoice-tasks' },
    { label: '待人工处理', value: (dashboard.value.pending_work_items || 0) + (dashboard.value.open_exceptions || 0), note: '待办与系统异常', tone: 'red', path: '/exceptions' },
  ]
})

async function loadDashboard() {
  try { dashboard.value = await getDashboardStats() } catch { dashboard.value = {} }
}
async function loadBatches() {
  batchLoading.value = true
  try { batches.value = (await getInvoiceBatches({ page: 1, page_size: 5 })).items } finally { batchLoading.value = false }
}
async function loadWorkItems() {
  workLoading.value = true
  try { workItems.value = (await getWorkItems({ page: 1, page_size: 5, status: 'pending' })).items } finally { workLoading.value = false }
}
onMounted(() => { loadDashboard(); loadBatches(); loadWorkItems() })
</script>

<style scoped lang="scss">
.metric-row { margin-bottom: 16px; }.metric-card { min-height: 112px; padding:18px 20px; border:1px solid #e8edf5; background:#fff; border-radius:8px; cursor:pointer; display:flex; flex-direction:column; gap:6px; transition:box-shadow .2s; }.metric-card:hover{box-shadow:0 5px 16px rgba(16,24,40,.08)}.metric-card span{font-size:13px;color:#667085}.metric-card strong{font-size:28px;color:#1d2939}.metric-card small{font-size:12px;color:#98a2b3}.metric-card.blue strong{color:#2563eb}.metric-card.orange strong{color:#d97706}.metric-card.red strong{color:#dc2626}.content-card{border-radius:8px}.card-header{display:flex;justify-content:space-between;align-items:center}.success-text{color:#16a34a}.danger-text{color:#dc2626}.exception-button{width:100%;margin-top:16px}
</style>
