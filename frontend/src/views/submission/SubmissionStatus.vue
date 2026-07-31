<template>
  <div class="customer-submit-page">
    <div class="status-container">
      <div class="status-header">
        <div class="header-logo">
          <el-icon :size="28" color="#fff"><Document /></el-icon>
          <span>智能开票平台</span>
        </div>
        <p class="header-subtitle">开票进度查询</p>
      </div>

      <div class="status-body">
        <div class="query-block">
          <el-input v-model="requestNo" placeholder="请输入申请单号" size="large" clearable @keyup.enter="handleQuery">
            <template #append>
              <el-button :loading="loading" @click="handleQuery">查询</el-button>
            </template>
          </el-input>
        </div>

        <div v-if="loading" class="state-block">
          <el-icon class="is-loading" :size="32" color="#2563EB"><Loading /></el-icon>
          <p>正在查询...</p>
        </div>

        <div v-else-if="!result && queried" class="state-block">
          <el-empty description="未找到对应的申请记录，请检查单号是否正确" />
        </div>

        <div v-else-if="result" class="result-block">
          <div class="result-header">
            <div>
              <h3>申请单号：{{ result.request_no }}</h3>
              <p class="enterprise-name">{{ result.enterprise_name }}</p>
            </div>
            <el-tag :type="statusTagType(result.status)" size="large">{{ statusText(result.status) }}</el-tag>
          </div>

          <el-divider />

          <el-timeline class="result-timeline">
            <el-timeline-item
              v-for="(step, idx) in result.timeline"
              :key="idx"
              :type="step.status === 'done' ? 'success' : step.status === 'processing' ? 'primary' : 'info'"
              :timestamp="step.timestamp ? formatDateTime(step.timestamp) : '待处理'"
              :hollow="step.status === 'pending'"
              size="large"
            >
              <p class="timeline-label">{{ step.label }}</p>
              <p v-if="step.description" class="timeline-desc">{{ step.description }}</p>
            </el-timeline-item>
          </el-timeline>

          <div v-if="result.invoice_url || result.pdf_url" class="result-download">
            <p class="download-title">开票结果</p>
            <div class="download-buttons">
              <el-button v-if="result.invoice_url" type="primary" @click="downloadFile(result.invoice_url)">
                <el-icon><Download /></el-icon>下载发票
              </el-button>
              <el-button v-if="result.pdf_url" type="primary" @click="downloadFile(result.pdf_url)">
                <el-icon><Download /></el-icon>下载PDF
              </el-button>
            </div>
          </div>

          <el-alert
            v-if="result.error_message"
            type="error"
            :title="result.error_message"
            :closable="false"
            show-icon
            class="result-error"
          />
        </div>

        <div v-else class="state-block">
          <el-empty description="输入申请单号查询开票进度" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { Document, Loading, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getSubmissionStatus, type SubmissionStatusInfo } from '@/api/submission'
import { formatDateTime } from '@/utils/format'

const route = useRoute()
const token = computed(() => route.params.token as string)

const requestNo = ref((route.query.request_no as string) || '')
const loading = ref(false)
const queried = ref(false)
const result = ref<SubmissionStatusInfo | null>(null)

async function handleQuery() {
  if (!requestNo.value.trim()) {
    ElMessage.warning('请输入申请单号')
    return
  }
  loading.value = true
  queried.value = true
  result.value = null
  try {
    result.value = await getSubmissionStatus(token.value, requestNo.value.trim())
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

function downloadFile(url: string) {
  window.open(url, '_blank')
}

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'primary' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'primary' | 'danger'> = {
    completed: 'success',
    processing: 'primary',
    invoicing: 'primary',
    pending: 'info',
    failed: 'danger',
    awaiting_review: 'warning',
    approved: 'success'
  }
  return map[status] || 'info'
}

function statusText(status: string) {
  const map: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    awaiting_review: '待审核',
    approved: '已审核',
    invoicing: '开票中',
    completed: '已完成',
    failed: '已失败',
    cancelled: '已取消'
  }
  return map[status] || status
}
</script>

<style scoped lang="scss">
.customer-submit-page {
  min-height: 100vh;
  background: #f6f8fb;
  display: flex;
  justify-content: center;
  padding: 40px 20px;
}

.status-container {
  width: 100%;
  max-width: 640px;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.status-header {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  padding: 32px 40px;
  color: #fff;

  .header-logo {
    display: flex;
    align-items: center;
    gap: 10px;

    span {
      font-size: 20px;
      font-weight: 600;
    }
  }

  .header-subtitle {
    margin-top: 8px;
    font-size: 14px;
    opacity: 0.85;
  }
}

.status-body {
  padding: 32px 40px;
}

.query-block {
  margin-bottom: 24px;
}

.state-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
  color: #6b7280;

  p {
    margin-top: 16px;
  }
}

.result-block {
  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    h3 {
      font-size: 18px;
      color: #1f2937;
      margin: 0 0 4px 0;
    }

    .enterprise-name {
      font-size: 13px;
      color: #6b7280;
      margin: 0;
    }
  }

  .result-timeline {
    padding-left: 0;
    margin-top: 8px;

    .timeline-label {
      font-size: 15px;
      color: #1f2937;
      margin: 0;
      font-weight: 500;
    }

    .timeline-desc {
      font-size: 13px;
      color: #6b7280;
      margin-top: 4px;
    }
  }

  .result-download {
    padding: 16px 20px;
    background: #f0fdf4;
    border-radius: 8px;
    margin-top: 20px;

    .download-title {
      font-size: 14px;
      color: #1f2937;
      font-weight: 500;
      margin-bottom: 10px;
    }

    .download-buttons {
      display: flex;
      gap: 12px;
    }
  }

  .result-error {
    margin-top: 16px;
  }
}
</style>
