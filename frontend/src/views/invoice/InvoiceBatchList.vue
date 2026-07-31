<template>
  <div class="page-container batch-workbench">
    <PageHeader title="批量开票" subtitle="导入订单、自动开票、集中处理异常">
      <template #actions>
        <el-button @click="handleDownloadTemplate"><el-icon><Download /></el-icon>下载模板</el-button>
        <el-button type="primary" @click="importDialogVisible = true"><el-icon><Upload /></el-icon>Excel订单导入</el-button>
      </template>
    </PageHeader>

    <el-row :gutter="14" class="summary-row">
      <el-col :span="6"><div class="summary-card"><span>导入批次</span><strong>{{ pagination.total }}</strong></div></el-col>
      <el-col :span="6"><div class="summary-card success"><span>累计成功</span><strong>{{ summary.success }}</strong></div></el-col>
      <el-col :span="6"><div class="summary-card processing"><span>处理中</span><strong>{{ summary.processing }}</strong></div></el-col>
      <el-col :span="6"><div class="summary-card danger"><span>累计异常</span><strong>{{ summary.exceptions }}</strong></div></el-col>
    </el-row>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <div><strong>开票批次</strong><span>点击批次展开任务明细</span></div>
          <el-select v-model="filter.source_type" placeholder="全部来源" clearable size="small" style="width:130px" @change="handleSearch">
            <el-option label="Excel导入" value="excel" />
            <el-option label="图片录入" value="image" />
            <el-option label="文字录入" value="text" />
          </el-select>
        </div>
      </template>
      <el-table v-loading="loading" :data="tableData" stripe empty-text="暂无导入批次，点击右上角开始导入" @row-click="openDrawer">
        <el-table-column label="导入文件" min-width="220" show-overflow-tooltip>
          <template #default="{ row }"><div class="file-cell"><el-icon><Document /></el-icon><span>{{ row.file_name || '未命名导入' }}</span></div></template>
        </el-table-column>
        <el-table-column label="来源" width="100"><template #default="{ row }"><el-tag size="small" effect="plain">{{ sourceText(row.source_type) }}</el-tag></template></el-table-column>
        <el-table-column label="任务" width="70" align="center"><template #default="{ row }">{{ row.task_count || 0 }}</template></el-table-column>
        <el-table-column label="成功" width="70" align="center"><template #default="{ row }"><span class="text-success">{{ row.success_count || 0 }}</span></template></el-table-column>
        <el-table-column label="异常" width="70" align="center"><template #default="{ row }"><span :class="row.exception_count ? 'text-danger' : ''">{{ row.exception_count || 0 }}</span></template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{ row }"><StatusTag :status="batchStatus(row)" type="task" /></template></el-table-column>
        <el-table-column label="导入时间" width="160"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openDrawer(row)">查看任务</el-button>
            <el-button v-if="row.exception_count > 0" link type="danger" @click.stop="handleExportFailed(row)">导出失败</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination">
        <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.page_size" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next" @size-change="fetchBatches" @current-change="fetchBatches" />
      </div>
    </el-card>

    <!-- 导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="Excel订单导入" width="560px" destroy-on-close>
      <div class="import-guide">
        <div class="guide-step"><span>1</span><div><strong>下载标准模板</strong><p>按模板填写订单；"企业名称"列用于自动匹配销方企业。</p></div><el-button link type="primary" @click="handleDownloadTemplate">下载模板</el-button></div>
        <div class="guide-step"><span>2</span><div><strong>上传订单文件</strong><p>正常行自动开票，错误行不影响其他行。</p></div></div>
      </div>
      <el-upload drag accept=".xlsx" :auto-upload="false" :limit="1" :on-change="onFileChange" :on-remove="onFileRemove">
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将填写完成的Excel文件拖到此处，或<em>点击上传</em></div>
        <template #tip><div class="el-upload__tip">仅支持 .xlsx，必填列：购方名称、商品名称、数量、单价。</div></template>
      </el-upload>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!uploadFile" @click="submitImport">开始批量开票</el-button>
      </template>
    </el-dialog>

    <!-- 批次任务抽屉 -->
    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="70%" destroy-on-close>
      <div v-if="currentBatch" class="drawer-summary">
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="文件名">{{ currentBatch.file_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="导入时间">{{ formatDateTime(currentBatch.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="任务总数">{{ currentBatch.task_count || 0 }}</el-descriptions-item>
          <el-descriptions-item label="批次状态"><StatusTag :status="batchStatus(currentBatch)" type="task" /></el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="drawer-toolbar">
        <el-radio-group v-model="taskFilter" size="small" @change="fetchTasks">
          <el-radio-button value="">全部 ({{ currentBatch?.task_count || 0 }})</el-radio-button>
          <el-radio-button value="success">成功 ({{ currentBatch?.success_count || 0 }})</el-radio-button>
          <el-radio-button value="failed">失败 ({{ currentBatch?.failure_count || 0 }})</el-radio-button>
          <el-radio-button value="unknown">未知 ({{ unknownCount }})</el-radio-button>
        </el-radio-group>
        <div>
          <el-button v-if="failedCount > 0" size="small" @click="handleExportFailed(currentBatch)"><el-icon><Download /></el-icon>导出失败行</el-button>
          <el-button v-if="failedCount > 0" size="small" type="warning" @click="handleBatchRetry">批量重试失败</el-button>
        </div>
      </div>

      <el-table v-loading="taskLoading" :data="taskData" stripe border class="drawer-table" empty-text="该批次暂无任务">
        <el-table-column label="序号" width="60" type="index" />
        <el-table-column prop="buyer_name" label="购方名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="价税合计" width="120" align="right"><template #default="{ row }">¥{{ formatAmount(row.total_with_tax) }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }"><StatusTag :status="row.status" type="task" /></template></el-table-column>
        <el-table-column prop="invoice_number" label="发票号码" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.invoice_number || '-' }}</template>
        </el-table-column>
        <el-table-column label="失败原因" min-width="180" show-overflow-tooltip>
          <template #default="{ row }"><span class="text-danger">{{ row.last_error || '-' }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="router.push(`/invoice-tasks/${row.id}`)">详情</el-button>
            <el-button v-if="['failed','awaiting_manual'].includes(row.status)" link type="warning" size="small" @click="handleRetry(row)">重试</el-button>
            <el-button v-if="['pending_validation','validation_passed','pending_submit','queuing'].includes(row.status)" link type="danger" size="small" @click="handleCancel(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination v-model:current-page="taskPagination.page" v-model:page-size="taskPagination.page_size" :total="taskPagination.total" :page-sizes="[10,20,50]" layout="total, prev, pager, next" @current-change="fetchTasks" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Document, Download, Upload, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { getBatches, downloadBatchTemplate, getBatchTasks, exportFailedRows, retryBatchTask, cancelBatchTask } from '@/api/batch'
import { submitExcelRequest } from '@/api/invoice'
import { formatAmount, formatDateTime } from '@/utils/format'
import type { ImportBatch } from '@/types'

const router = useRouter()
const loading = ref(false)
const importing = ref(false)
const importDialogVisible = ref(false)
const uploadFile = ref<File | null>(null)
const tableData = ref<ImportBatch[]>([])
const filter = reactive({ source_type: '' })
const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const drawerVisible = ref(false)
const currentBatch = ref<ImportBatch | null>(null)
const taskLoading = ref(false)
const taskData = ref<any[]>([])
const taskFilter = ref('')
const taskPagination = reactive({ page: 1, page_size: 20, total: 0 })

const summary = computed(() => tableData.value.reduce((acc, b) => ({
  success: acc.success + (b.success_count || 0),
  processing: acc.processing + (b.status === 'processing' ? 1 : 0),
  exceptions: acc.exceptions + (b.exception_count || 0),
}), { success: 0, processing: 0, exceptions: 0 }))

const drawerTitle = computed(() => `批次任务明细 — ${currentBatch.value?.file_name || ''}`)
const failedCount = computed(() => taskData.value.filter(t => ['failed','awaiting_manual'].includes(t.status)).length)
const unknownCount = computed(() => taskData.value.filter(t => t.status === 'unknown').length)

function sourceText(s: string) { return ({ excel:'Excel导入', image:'图片录入', text:'文字录入' } as Record<string,string>)[s] || s }
function batchStatus(b: ImportBatch) {
  if (b.status === 'completed') return 'success'
  if (b.status === 'failed') return 'failed'
  if (b.status === 'partial') return 'awaiting_manual'
  return 'queuing'
}

async function fetchBatches() {
  loading.value = true
  try {
    const res = await getBatches({ page: pagination.page, page_size: pagination.page_size, source_type: filter.source_type || undefined })
    tableData.value = res.items
    pagination.total = res.total
  } finally { loading.value = false }
}

function handleSearch() { pagination.page = 1; fetchBatches() }

async function openDrawer(batch: ImportBatch) {
  currentBatch.value = batch
  taskFilter.value = ''
  taskPagination.page = 1
  drawerVisible.value = true
  await fetchTasks()
}

async function fetchTasks() {
  if (!currentBatch.value) return
  taskLoading.value = true
  try {
    const res = await getBatchTasks(currentBatch.value.id, { page: taskPagination.page, page_size: taskPagination.page_size, status: taskFilter.value || undefined })
    taskData.value = res.items
    taskPagination.total = res.total
  } finally { taskLoading.value = false }
}

function onFileChange(file: any) { uploadFile.value = file.raw }
function onFileRemove() { uploadFile.value = null }

async function handleDownloadTemplate() {
  try {
    const res: any = await downloadBatchTemplate()
    const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = '批量开票导入模板.xlsx'
    link.click()
    URL.revokeObjectURL(link.href)
  } catch { ElMessage.error('模板下载失败') }
}

async function submitImport() {
  if (!uploadFile.value) return
  importing.value = true
  try {
    const res: any = await submitExcelRequest({ file: uploadFile.value })
    const count = res.invoice_tasks?.length || 0
    ElMessage.success(`导入完成，已创建 ${count} 个开票任务`)
    importDialogVisible.value = false
    uploadFile.value = null
    await fetchBatches()
    if (tableData.value[0]) openDrawer(tableData.value[0])
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error((typeof detail === 'object' ? detail.message : detail) || '导入失败')
  } finally { importing.value = false }
}

async function handleExportFailed(batch: ImportBatch | null) {
  if (!batch) return
  try {
    const res: any = await exportFailedRows(batch.id)
    const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `失败任务_${batch.file_name || batch.id.slice(0,8)}.xlsx`
    link.click()
    URL.revokeObjectURL(link.href)
  } catch { ElMessage.error('导出失败') }
}

async function handleRetry(row: any) {
  try {
    await retryBatchTask(row.id)
    ElMessage.success('已提交重试')
    fetchTasks()
  } catch { /* interceptor handles */ }
}

async function handleCancel(row: any) {
  try {
    await ElMessageBox.confirm('确定取消该任务？', '提示', { type: 'warning' })
    await cancelBatchTask(row.id)
    ElMessage.success('任务已取消')
    fetchTasks()
  } catch { /* cancelled */ }
}

async function handleBatchRetry() {
  const failed = taskData.value.filter(t => ['failed','awaiting_manual'].includes(t.status))
  if (!failed.length) return
  try {
    await ElMessageBox.confirm(`将重试 ${failed.length} 个失败任务，确定继续？`, '批量重试', { type: 'warning' })
    let ok = 0
    for (const t of failed) {
      try { await retryBatchTask(t.id); ok++ } catch { /* skip */ }
    }
    ElMessage.success(`已重试 ${ok}/${failed.length} 个任务`)
    fetchTasks()
  } catch { /* cancelled */ }
}

onMounted(fetchBatches)
</script>

<style scoped lang="scss">
.summary-row { margin-bottom: 16px; }
.summary-card { height: 84px; padding: 16px 20px; background: #fff; border: 1px solid #e8edf5; border-radius: 8px; display: flex; flex-direction: column; gap: 6px; color: #667085; }
.summary-card strong { color: #1d2939; font-size: 24px; }
.summary-card.success strong, .text-success { color: #16a34a; }
.summary-card.processing strong { color: #2563eb; }
.summary-card.danger strong, .text-danger { color: #dc2626; }
.table-card { border-radius: 8px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header div { display: flex; align-items: baseline; gap: 10px; }
.card-header span { color: #98a2b3; font-size: 13px; }
.file-cell { display: flex; align-items: center; gap: 8px; color: #344054; cursor: pointer; }
.pagination { display: flex; justify-content: flex-end; margin-top: 12px; }
.import-guide { background: #f8faff; padding: 12px 14px; border-radius: 6px; margin-bottom: 16px; }
.guide-step { display: flex; align-items: center; gap: 10px; margin: 8px 0; }
.guide-step > span { width: 22px; height: 22px; line-height: 22px; text-align: center; border-radius: 50%; background: #2563eb; color: #fff; font-size: 12px; }
.guide-step div { flex: 1; }
.guide-step p { margin: 3px 0 0; color: #667085; font-size: 12px; }
.drawer-summary { margin-bottom: 16px; }
.drawer-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.drawer-table { margin-bottom: 12px; }
</style>
