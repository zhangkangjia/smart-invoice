<template>
  <div class="page-container">
    <PageHeader title="文字开票" subtitle="输入开票描述，AI自动识别并开票" />

    <el-row :gutter="16">
      <!-- 左侧输入 -->
      <el-col :span="12">
        <el-card shadow="never" class="input-card">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>开票描述</span>
              <el-button text size="small" @click="insertExample">填入示例</el-button>
            </div>
          </template>

          <el-input
            v-model="content"
            type="textarea"
            :rows="14"
            placeholder="直接输入开票描述，例如：&#10;&#10;给深圳腾讯科技有限公司开技术咨询费50000元，税率6%，发票发到 finance@tencent.com&#10;&#10;也可以一次输入多条：&#10;1. 给甲公司开服务费10000元，6%&#10;2. 给乙公司开咨询费8000元，6%，发到 billing@yi.com"
            style="font-size: 15px; line-height: 1.8;"
          />

          <div style="margin-top: 16px; display: flex; gap: 12px; align-items: center;">
            <el-button type="primary" size="large" :loading="submitting" @click="handleSubmit" style="flex: 1">
              <el-icon><Promotion /></el-icon>&nbsp;智能开票
            </el-button>
            <el-button size="large" @click="handleClear">清空</el-button>
          </div>

          <!-- 快捷提示 -->
          <div v-if="!content" class="quick-tips">
            <el-divider content-position="center">快捷示例</el-divider>
            <div class="tip-list">
              <div class="tip-item" @click="content = '给北京阿里巴巴科技有限公司开技术服务费30000元，税率6%，发到 invoice@alibaba.com'">
                给北京阿里巴巴科技有限公司开技术服务费30000元，税率6%
              </div>
              <div class="tip-item" @click="content = '给上海字节跳动开广告费120000元，税率6%'">
                给上海字节跳动开广告费120000元，税率6%
              </div>
              <div class="tip-item" @click="content = '1. 给甲公司开服务费10000元，6%\n2. 给乙公司开咨询费8000元，6%\n3. 给丙公司开设计费15000元，6%'">
                批量开票（3条）
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧结果 -->
      <el-col :span="12">
        <el-card shadow="never" class="result-card">
          <template #header>
            <span>识别与开票结果</span>
          </template>

          <div v-if="!result" class="result-empty">
            <el-empty description="输入开票描述后点击「智能开票」" />
          </div>

          <div v-else class="result-content">
            <!-- 企业匹配 -->
            <div class="result-section">
              <div class="section-title">
                <el-icon color="#2563EB"><OfficeBuilding /></el-icon>
                销方企业（自动匹配）
              </div>
              <div v-if="result.enterprise" class="matched-box success">
                <span>{{ result.enterprise.name }}</span>
                <el-tag size="small" type="success">已匹配</el-tag>
              </div>
              <div v-else class="matched-box warning">
                <span>未自动匹配到企业</span>
                <el-select
                  v-model="selectedEnterpriseId"
                  placeholder="请选择销方企业"
                  filterable
                  size="small"
                  style="width: 200px"
                  @change="onEnterpriseSelect"
                >
                  <el-option v-for="e in enterprises" :key="e.id" :label="e.name" :value="e.id" />
                </el-select>
              </div>
            </div>

            <!-- 客户匹配 -->
            <div class="result-section">
              <div class="section-title">
                <el-icon color="#2563EB"><User /></el-icon>
                购方客户（AI识别）
              </div>
              <div v-if="result.buyer_name" class="matched-box success">
                <div>
                  <span style="font-weight: 600;">{{ result.buyer_name }}</span>
                  <span v-if="result.buyer_tax_no" style="color: #909399; margin-left: 8px; font-size: 13px;">
                    税号: {{ result.buyer_tax_no }}
                  </span>
                  <span v-if="result.buyer_matched" style="margin-left: 8px;">
                    <el-tag size="small" type="success">历史客户</el-tag>
                  </span>
                </div>
              </div>
              <div v-else class="matched-box warning">
                <span>未识别到客户名称</span>
              </div>
            </div>

            <!-- 发票明细 -->
            <div class="result-section">
              <div class="section-title">
                <el-icon color="#2563EB"><Document /></el-icon>
                发票明细
              </div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="商品名称">{{ result.product_name || '-' }}</el-descriptions-item>
                <el-descriptions-item label="税率">{{ formatTaxRate(result.tax_rate) }}</el-descriptions-item>
                <el-descriptions-item label="不含税金额">¥{{ formatAmount(result.total_amount) }}</el-descriptions-item>
                <el-descriptions-item label="税额">¥{{ formatAmount(result.total_tax) }}</el-descriptions-item>
                <el-descriptions-item label="价税合计">
                  <span style="color: #2563EB; font-weight: 600; font-size: 16px;">¥{{ formatAmount(result.total_with_tax) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="接收邮箱">{{ result.receiver_email || '-' }}</el-descriptions-item>
              </el-descriptions>
            </div>

            <!-- 字段置信度 -->
            <div v-if="result.fields && result.fields.length" class="result-section">
              <div class="section-title">
                <el-icon color="#2563EB"><DataAnalysis /></el-icon>
                AI识别置信度
              </div>
              <div class="confidence-list">
                <div v-for="f in result.fields" :key="f.field_name" class="confidence-item">
                  <span class="conf-name">{{ fieldLabel(f.field_name) }}</span>
                  <el-progress
                    :percentage="Math.round(f.confidence * 100)"
                    :color="f.confidence > 0.85 ? '#67C23A' : f.confidence > 0.6 ? '#E6A23C' : '#F56C6C'"
                    :stroke-width="8"
                    style="flex: 1; margin: 0 8px;"
                  />
                  <el-tag size="small" :type="f.source === 'knowledge_base' ? 'success' : 'info'">
                    {{ sourceLabel(f.source) }}
                  </el-tag>
                </div>
              </div>
            </div>

            <!-- 开票结果 -->
            <div v-if="result.task" class="result-section">
              <div class="section-title">
                <el-icon color="#2563EB"><CircleCheck /></el-icon>
                开票结果
              </div>
              <div class="invoice-result-box" :class="result.task.status">
                <div v-if="result.task.status === 'success'" class="success-result">
                  <el-icon color="#67C23A" :size="20"><CircleCheckFilled /></el-icon>
                  <span style="margin-left: 8px;">开票成功</span>
                  <span style="margin-left: 16px; color: #909399;">发票号: {{ result.task.invoice_number }}</span>
                </div>
                <div v-else-if="result.task.status === 'failed'" class="failed-result">
                  <el-icon color="#F56C6C" :size="20"><CircleCloseFilled /></el-icon>
                  <span style="margin-left: 8px;">开票失败: {{ result.task.last_error }}</span>
                </div>
                <div v-else class="pending-result">
                  <el-icon color="#409EFF" :size="20"><Loading /></el-icon>
                  <span style="margin-left: 8px;">状态: {{ formatStatus(result.task.status) }}</span>
                </div>
              </div>
            </div>

            <!-- 操作 -->
            <div v-if="result.task && result.task.status === 'success'" style="text-align: center; margin-top: 16px;">
              <el-button type="primary" @click="handleViewTask(result.task.task_id)">查看任务详情</el-button>
              <el-button @click="handleClear">继续开票</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Promotion, OfficeBuilding, User, Document, DataAnalysis,
  CircleCheck, CircleCheckFilled, CircleCloseFilled, Loading
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { submitTextRequest } from '@/api/invoice'
import { getEnterprises } from '@/api/enterprise'
import { formatAmount, formatTaxRate, formatStatus } from '@/utils/format'
import type { Enterprise } from '@/types'

const router = useRouter()

const content = ref('')
const submitting = ref(false)
const result = ref<any>(null)
const enterprises = ref<Enterprise[]>([])
const selectedEnterpriseId = ref('')

async function fetchEnterprises() {
  try {
    const res = await getEnterprises({ page: 1, page_size: 100 })
    enterprises.value = res.items
  } catch {
    enterprises.value = []
  }
}

function insertExample() {
  content.value = '给深圳腾讯科技有限公司开技术咨询费50000元，税率6%，发票发到 finance@tencent.com'
}

async function handleSubmit() {
  if (!content.value.trim()) {
    ElMessage.warning('请输入开票描述')
    return
  }
  submitting.value = true
  result.value = null
  try {
    const res = await submitTextRequest({
      enterprise_id: selectedEnterpriseId.value || enterprises.value[0]?.id || '',
      content: content.value,
    })

    // 解析返回的业务申请详情
    const tasks = res.invoice_tasks || []
    const task = tasks[0]
    const ocr = res.source_documents?.[0]?.ocr_result || {}
    const fields = ocr.fields || []

    // 从识别字段提取值
    const getField = (name: string) => fields.find((f: any) => f.field_name === name)?.value

    result.value = {
      enterprise: enterprises.value.find(e => e.id === res.enterprise_id) || { name: res.enterprise_id },
      buyer_name: getField('buyer_name') || task?.buyer_name,
      buyer_tax_no: getField('buyer_tax_no'),
      buyer_matched: fields.some((f: any) => f.field_name === 'buyer_name' && f.source === 'knowledge_base'),
      product_name: getField('product_name'),
      tax_rate: getField('tax_rate'),
      total_amount: task?.total_with_tax ? task.total_with_tax / 1.06 : 0,
      total_tax: task?.total_with_tax ? task.total_with_tax - task.total_with_tax / 1.06 : 0,
      total_with_tax: task?.total_with_tax || 0,
      receiver_email: getField('receiver_email'),
      fields: fields,
      task: task ? {
        task_id: task.task_id,
        status: task.task_status,
        invoice_number: task.invoice_number,
        last_error: task.last_error,
      } : null,
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '开票失败')
  } finally {
    submitting.value = false
  }
}

function onEnterpriseSelect(val: string) {
  selectedEnterpriseId.value = val
}

function handleClear() {
  content.value = ''
  result.value = null
}

function handleViewTask(taskId: string) {
  router.push(`/invoice-tasks/${taskId}`)
}

function fieldLabel(name: string): string {
  const labels: Record<string, string> = {
    buyer_name: '购方名称',
    buyer_tax_no: '购方税号',
    product_name: '商品名称',
    total_with_tax: '价税合计',
    tax_rate: '税率',
    receiver_email: '接收邮箱',
    receiver_mobile: '手机号',
    invoice_type: '发票类型',
    remark: '备注',
    external_order_no: '订单号',
  }
  return labels[name] || name
}

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    llm: 'AI',
    ocr: 'OCR',
    multimodal: '多模态',
    rule: '规则',
    knowledge_base: '知识库',
  }
  return labels[source] || source
}

onMounted(() => {
  fetchEnterprises()
})
</script>

<style scoped lang="scss">
.input-card, .result-card {
  border-radius: 8px;
  min-height: 600px;
}

.result-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 500px;
}

.result-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.result-section {
  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 8px;
  }
}

.matched-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 14px;

  &.success {
    background: #f0f9eb;
    border: 1px solid #c2e7b0;
  }
  &.warning {
    background: #fdf6ec;
    border: 1px solid #f5dab1;
  }
}

.confidence-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.confidence-item {
  display: flex;
  align-items: center;

  .conf-name {
    width: 90px;
    font-size: 13px;
    color: #606266;
  }
}

.invoice-result-box {
  padding: 16px;
  border-radius: 8px;
  text-align: center;
  font-size: 15px;

  &.success {
    background: #f0f9eb;
    border: 1px solid #67C23A;
  }
  &.failed {
    background: #fef0f0;
    border: 1px solid #F56C6C;
  }
  &.unknown, &.submitting, &.queuing, &.pending_submit, &.accepted {
    background: #ecf5ff;
    border: 1px solid #409EFF;
  }
}

.quick-tips {
  margin-top: 8px;
}

.tip-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tip-item {
  padding: 10px 14px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
  color: #606266;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #e4e7ed;

  &:hover {
    background: #ecf5ff;
    border-color: #409EFF;
    color: #409EFF;
  }
}
</style>
