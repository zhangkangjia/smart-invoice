<template>
  <div class="page-container">
    <PageHeader :title="task ? `开票任务 ${shortId(task.id)}` : '任务详情'" subtitle="开票任务、发票明细与执行轨迹">
      <template #actions>
        <el-button @click="router.back()">返回</el-button>
        <el-button v-if="task?.status === 'failed'" type="warning" @click="handleRetry">重试</el-button>
        <el-button v-if="task && cancellableStatuses.includes(task.status)" type="danger" @click="handleCancel">取消任务</el-button>
      </template>
    </PageHeader>

    <el-skeleton v-if="loading" :rows="10" animated />

    <el-alert
      v-else-if="loadError"
      :title="loadError"
      type="error"
      show-icon
      :closable="false"
    />

    <template v-else-if="task">
      <el-row :gutter="16">
        <el-col :span="16">
          <el-card shadow="never" class="detail-card">
            <template #header><span>任务基本信息</span></template>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="任务ID">{{ task.id }}</el-descriptions-item>
              <el-descriptions-item label="所属企业">{{ task.enterprise_name || '-' }}</el-descriptions-item>
              <el-descriptions-item label="销方税号">{{ task.enterprise_tax_no || '-' }}</el-descriptions-item>
              <el-descriptions-item label="当前状态"><StatusTag :status="task.status" type="task" /></el-descriptions-item>
              <el-descriptions-item label="重试次数">{{ task.retry_count || 0 }} / {{ task.max_retries || 3 }}</el-descriptions-item>
              <el-descriptions-item label="通道提交号">{{ task.channel_submission_id || '-' }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatDateTime(task.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="完成时间">{{ formatDateTime(task.completed_at) }}</el-descriptions-item>
            </el-descriptions>
            <el-alert v-if="task.last_error" :title="task.last_error" type="error" :closable="false" show-icon class="error-message" />
          </el-card>

          <el-card v-if="invoice" shadow="never" class="detail-card">
            <template #header><span>发票明细</span></template>
            <el-descriptions :column="2" border style="margin-bottom: 16px">
              <el-descriptions-item label="发票号码">{{ invoiceResult?.invoice_number || '等待通道返回' }}</el-descriptions-item>
              <el-descriptions-item label="发票类型">{{ invoice.invoice_type || '-' }}</el-descriptions-item>
              <el-descriptions-item label="购方名称">{{ invoice.buyer_name || '-' }}</el-descriptions-item>
              <el-descriptions-item label="购方税号">{{ invoice.buyer_tax_no || '-' }}</el-descriptions-item>
              <el-descriptions-item label="不含税金额">¥{{ formatAmount(invoice.total_amount) }}</el-descriptions-item>
              <el-descriptions-item label="税额">¥{{ formatAmount(invoice.total_tax) }}</el-descriptions-item>
              <el-descriptions-item label="价税合计"><strong class="amount">¥{{ formatAmount(invoice.total_with_tax) }}</strong></el-descriptions-item>
              <el-descriptions-item label="接收邮箱">{{ invoice.receiver_email || '-' }}</el-descriptions-item>
              <el-descriptions-item label="备注" :span="2">{{ invoice.remark || '-' }}</el-descriptions-item>
            </el-descriptions>

            <el-table :data="invoice.items || []" border stripe empty-text="暂无商品明细">
              <el-table-column prop="product_name" label="商品名称" min-width="180" show-overflow-tooltip />
              <el-table-column prop="tax_code" label="税收编码" width="140" show-overflow-tooltip />
              <el-table-column prop="spec" label="规格" width="110" />
              <el-table-column prop="unit" label="单位" width="70" />
              <el-table-column prop="quantity" label="数量" width="90" align="right" />
              <el-table-column label="单价" width="110" align="right"><template #default="{ row }">¥{{ formatAmount(row.unit_price) }}</template></el-table-column>
              <el-table-column label="金额" width="110" align="right"><template #default="{ row }">¥{{ formatAmount(row.amount) }}</template></el-table-column>
              <el-table-column label="税率" width="90"><template #default="{ row }">{{ formatTaxRate(row.tax_rate * 100) }}</template></el-table-column>
              <el-table-column label="税额" width="110" align="right"><template #default="{ row }">¥{{ formatAmount(row.tax_amount) }}</template></el-table-column>
            </el-table>
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card shadow="never" class="detail-card">
            <template #header><span>状态时间线</span></template>
            <el-timeline v-if="timeline.length">
              <el-timeline-item
                v-for="(item, index) in timeline"
                :key="`${item.created_at}-${index}`"
                :timestamp="formatDateTime(item.created_at)"
                placement="top"
                :type="getTimelineType(item.status)"
              >
                <p class="timeline-title">{{ item.action }}</p>
                <p class="timeline-desc">操作人：{{ item.operator_name || '系统' }}</p>
                <p v-if="item.remark" class="timeline-remark">{{ item.remark }}</p>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无时间线数据" :image-size="80" />
          </el-card>

          <el-card shadow="never" class="detail-card">
            <template #header><span>开票结果与交付</span></template>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="发票号码">{{ invoiceResult?.invoice_number || '-' }}</el-descriptions-item>
              <el-descriptions-item label="文件状态">{{ invoiceResult?.file_status || '未生成' }}</el-descriptions-item>
              <el-descriptions-item label="结果校验">{{ invoiceResult?.verified ? '已校验' : '待校验' }}</el-descriptions-item>
            </el-descriptions>
          </el-card>

          <el-card shadow="never" class="detail-card">
            <template #header><span>审计轨迹</span></template>
            <el-table :data="activityLogs" size="small" border empty-text="暂无审计记录">
              <el-table-column prop="action" label="操作" min-width="120" show-overflow-tooltip />
              <el-table-column prop="operator" label="操作人" width="100"><template #default="{ row }">{{ row.operator || '系统' }}</template></el-table-column>
              <el-table-column label="时间" width="145"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { getInvoiceTask, retryInvoiceTask, cancelInvoiceTask } from '@/api/invoice'
import { formatAmount, formatDateTime, formatTaxRate } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id as string
const loading = ref(false)
const loadError = ref('')
const task = ref<any>(null)
const cancellableStatuses = ['pending_validation', 'validation_passed', 'pending_submit', 'queuing', 'awaiting_manual']

const invoice = computed(() => task.value?.invoice_request || null)
const invoiceResult = computed(() => task.value?.invoice_result || null)
const timeline = computed(() => task.value?.timeline || [])
const auditLogs = computed(() => task.value?.audit_logs || [])
// 老任务可能没有写入独立审计表；此时复用状态时间线展示系统执行轨迹。
const activityLogs = computed(() => {
  if (auditLogs.value.length) {
    return auditLogs.value.map((item: any) => ({
      action: item.action,
      operator: item.user_id || '系统',
      created_at: item.created_at,
    }))
  }
  return timeline.value.map((item: any) => ({
    action: item.action,
    operator: item.operator_name || '系统',
    created_at: item.created_at,
  }))
})

function shortId(id: string) {
  return id ? `${id.slice(0, 8)}…` : ''
}

function getTimelineType(status: string) {
  if (status === 'success') return 'success'
  if (['failed', 'terminated', 'awaiting_manual'].includes(status)) return 'danger'
  if (['unknown', 'awaiting_reconciliation', 'confirming'].includes(status)) return 'warning'
  return 'primary'
}

async function fetchTask() {
  loading.value = true
  loadError.value = ''
  try {
    task.value = await getInvoiceTask(taskId)
  } catch (error: any) {
    loadError.value = error?.response?.data?.detail || error?.message || '加载任务详情失败'
  } finally {
    loading.value = false
  }
}

async function handleRetry() {
  try {
    await ElMessageBox.confirm('确定要重新提交此开票任务吗？', '重试任务', { type: 'warning' })
    await retryInvoiceTask(taskId)
    ElMessage.success('已加入重试队列')
    await fetchTask()
  } catch {
    // 用户取消或请求失败已由拦截器提示
  }
}

async function handleCancel() {
  try {
    await ElMessageBox.confirm('取消后未提交的开票任务将终止，确定继续吗？', '取消任务', { type: 'warning' })
    await cancelInvoiceTask(taskId)
    ElMessage.success('任务已取消')
    await fetchTask()
  } catch {
    // 用户取消或请求失败已由拦截器提示
  }
}

onMounted(fetchTask)
</script>

<style scoped lang="scss">
.detail-card { border-radius: 8px; margin-bottom: 16px; }
.error-message { margin-top: 16px; }
.amount { color: #2563eb; font-size: 16px; }
.timeline-title { font-weight: 600; margin: 0 0 4px; }
.timeline-desc { font-size: 13px; color: #6b7280; margin: 2px 0; }
.timeline-remark { font-size: 13px; color: #6b7280; margin: 6px 0 0; padding: 5px 8px; background: #f6f8fb; border-radius: 4px; word-break: break-word; }
</style>
