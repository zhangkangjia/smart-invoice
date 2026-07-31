<template>
  <div class="customer-submit-page">
    <div class="submit-container">
      <!-- 头部 -->
      <div class="submit-header">
        <div class="header-logo">
          <el-icon :size="28" color="#fff"><Document /></el-icon>
          <span>智能开票平台</span>
        </div>
        <p class="header-subtitle">开票资料提交</p>
      </div>

      <div class="submit-body">
        <!-- 加载中 -->
        <div v-if="loadingInfo" class="state-block">
          <el-icon class="is-loading" :size="32" color="#2563EB"><Loading /></el-icon>
          <p>正在加载...</p>
        </div>

        <!-- 链接无效 -->
        <el-result
          v-else-if="!submissionInfo || !submissionInfo.is_active"
          icon="error"
          title="链接不可用"
          sub-title="该提交链接已失效或被停用，请联系服务方获取新的链接"
        />

        <!-- 需要密码 -->
        <div v-else-if="submissionInfo.requires_password && !authenticated" class="auth-block">
          <el-card shadow="never" class="auth-card">
            <h3>请输入访问密码</h3>
            <p class="auth-tip">企业：{{ maskedEnterpriseName }}</p>
            <el-input
              v-model="password"
              type="password"
              placeholder="请输入密码"
              show-password
              size="large"
              @keyup.enter="handleAuth"
            />
            <el-button type="primary" size="large" class="auth-btn" :loading="authing" @click="handleAuth">
              验证
            </el-button>
          </el-card>
        </div>

        <!-- 提交表单 -->
        <div v-else class="form-block">
          <div class="enterprise-info">
            <el-icon :size="20" color="#2563EB"><OfficeBuilding /></el-icon>
            <span>{{ maskedEnterpriseName }}</span>
          </div>

          <el-tabs v-model="activeTab" class="submit-tabs">
            <el-tab-pane label="提交资料" name="submit">
              <el-form ref="formRef" :model="form" label-position="top" class="submit-form">
                <el-form-item label="开票需求描述">
                  <el-input
                    v-model="form.content"
                    type="textarea"
                    :rows="4"
                    placeholder="请描述您的开票需求，例如：请开具一张电子普通发票，金额5000元，明细为咨询服务费"
                  />
                </el-form-item>

                <el-form-item label="上传文件（图片或Excel）">
                  <el-upload
                    drag
                    multiple
                    accept="image/*,.xlsx,.xls,.csv"
                    :auto-upload="false"
                    :file-list="fileList"
                    :on-change="handleFileChange"
                    :on-remove="handleFileRemove"
                  >
                    <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                    <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
                    <template #tip>
                      <div class="el-upload__tip">支持图片（JPG/PNG）和 Excel 文件，单个文件不超过 10MB</div>
                    </template>
                  </el-upload>
                </el-form-item>

                <el-form-item label="外部单号（选填）">
                  <el-input v-model="form.external_order_no" placeholder="如有订单号可填写，便于双方核对" />
                </el-form-item>

                <el-form-item label="备注（选填）">
                  <el-input v-model="form.customer_remark" type="textarea" :rows="2" placeholder="其他需要说明的事项" />
                </el-form-item>

                <el-divider content-position="left">联系信息</el-divider>

                <el-row :gutter="16">
                  <el-col :span="8">
                    <el-form-item label="联系人姓名">
                      <el-input v-model="form.contact_name" placeholder="您的姓名" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="8">
                    <el-form-item label="手机号码">
                      <el-input v-model="form.contact_phone" placeholder="手机号码" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="8">
                    <el-form-item label="邮箱">
                      <el-input v-model="form.contact_email" placeholder="电子邮箱" />
                    </el-form-item>
                  </el-col>
                </el-row>

                <div class="submit-actions">
                  <el-button type="primary" size="large" :loading="submitting" :disabled="!canSubmit" @click="handleSubmit">
                    提交开票申请
                  </el-button>
                </div>
              </el-form>
            </el-tab-pane>

            <el-tab-pane label="查询进度" name="status">
              <div class="status-query">
                <el-input v-model="queryRequestId" placeholder="请输入申请单号" size="large" clearable>
                  <template #append>
                    <el-button :loading="querying" @click="handleQueryStatus">查询</el-button>
                  </template>
                </el-input>

                <div v-if="historyList.length > 0" class="history-list">
                  <p class="history-title">最近提交记录</p>
                  <div
                    v-for="item in historyList"
                    :key="item.request_id"
                    class="history-item"
                    @click="queryRequestId = item.request_no; handleQueryStatus()"
                  >
                    <span class="history-item__no">{{ item.request_no }}</span>
                    <el-tag :type="statusTagType(item.status)" size="small">{{ statusText(item.status) }}</el-tag>
                    <span class="history-item__time">{{ formatDateTime(item.created_at) }}</span>
                  </div>
                </div>

                <div v-if="queryResult" class="query-result">
                  <el-divider />
                  <div class="result-header">
                    <h4>申请单号：{{ queryResult.request_no }}</h4>
                    <el-tag :type="statusTagType(queryResult.status)" size="default">{{ statusText(queryResult.status) }}</el-tag>
                  </div>
                  <el-timeline class="result-timeline">
                    <el-timeline-item
                      v-for="(step, idx) in queryResult.timeline"
                      :key="idx"
                      :type="step.status === 'done' ? 'success' : step.status === 'processing' ? 'primary' : 'info'"
                      :timestamp="step.timestamp ? formatDateTime(step.timestamp) : '待处理'"
                      :hollow="step.status === 'pending'"
                    >
                      <p class="timeline-label">{{ step.label }}</p>
                      <p v-if="step.description" class="timeline-desc">{{ step.description }}</p>
                    </el-timeline-item>
                  </el-timeline>

                  <div v-if="queryResult.invoice_url || queryResult.pdf_url" class="result-download">
                    <p>开票结果：</p>
                    <el-button v-if="queryResult.invoice_url" type="primary" link @click="downloadFile(queryResult.invoice_url, '发票')">
                      <el-icon><Download /></el-icon>下载发票
                    </el-button>
                    <el-button v-if="queryResult.pdf_url" type="primary" link @click="downloadFile(queryResult.pdf_url, 'PDF')">
                      <el-icon><Download /></el-icon>下载PDF
                    </el-button>
                  </div>

                  <el-alert
                    v-if="queryResult.error_message"
                    type="error"
                    :title="queryResult.error_message"
                    :closable="false"
                    show-icon
                    class="result-error"
                  />
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>

      <!-- 提交成功提示 -->
      <el-dialog v-model="successVisible" title="提交成功" width="440px" :close-on-click-modal="false">
        <div class="success-content">
          <el-icon :size="48" color="#10B981"><CircleCheckFilled /></el-icon>
          <p class="success-title">您的开票申请已提交成功</p>
          <p class="success-no">申请单号：<strong>{{ submittedRequestNo }}</strong></p>
          <p class="success-tip">请保存此单号，您可以使用它查询开票进度</p>
        </div>
        <template #footer>
          <el-button @click="successVisible = false">继续提交</el-button>
          <el-button type="primary" @click="goToStatus">查询进度</el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Document, OfficeBuilding, UploadFilled, Loading, Download, CircleCheckFilled } from '@element-plus/icons-vue'
import { ElMessage, type UploadFile } from 'element-plus'
import {
  getSubmissionInfo,
  authSubmission,
  submitViaLink,
  getSubmissionStatus,
  getSubmissionHistory,
  type SubmissionInfo,
  type SubmissionStatusInfo,
  type SubmissionHistoryItem
} from '@/api/submission'
import { formatDateTime } from '@/utils/format'

const route = useRoute()
const token = computed(() => route.params.token as string)

const loadingInfo = ref(true)
const authing = ref(false)
const submitting = ref(false)
const querying = ref(false)
const authenticated = ref(false)
const password = ref('')
const activeTab = ref('submit')
const successVisible = ref(false)
const submittedRequestNo = ref('')

const submissionInfo = ref<SubmissionInfo | null>(null)
const fileList = ref<UploadFile[]>([])
const form = reactive({
  content: '',
  external_order_no: '',
  customer_remark: '',
  contact_name: '',
  contact_phone: '',
  contact_email: ''
})

const queryRequestId = ref('')
const queryResult = ref<SubmissionStatusInfo | null>(null)
const historyList = ref<SubmissionHistoryItem[]>([])

const maskedEnterpriseName = computed(() => {
  const name = submissionInfo.value?.enterprise_name || ''
  if (name.length <= 2) return name + '*'
  return name.charAt(0) + '*'.repeat(Math.min(name.length - 2, 4)) + name.charAt(name.length - 1)
})

const canSubmit = computed(() => {
  return form.content.trim() || fileList.value.length > 0
})

async function fetchInfo() {
  loadingInfo.value = true
  try {
    submissionInfo.value = await getSubmissionInfo(token.value)
  } catch {
    submissionInfo.value = null
  } finally {
    loadingInfo.value = false
  }
}

async function handleAuth() {
  if (!password.value) {
    ElMessage.warning('请输入密码')
    return
  }
  authing.value = true
  try {
    await authSubmission(token.value, password.value)
    authenticated.value = true
    ElMessage.success('验证成功')
  } catch {
    // ignore
  } finally {
    authing.value = false
  }
}

function handleFileChange(file: UploadFile) {
  fileList.value.push(file)
}

function handleFileRemove(file: UploadFile) {
  fileList.value = fileList.value.filter((f) => f.uid !== file.uid)
}

async function handleSubmit() {
  if (!canSubmit.value) {
    ElMessage.warning('请填写开票需求或上传文件')
    return
  }
  submitting.value = true
  try {
    const files = fileList.value.map((f) => f.raw as File).filter(Boolean)
    const res = await submitViaLink(token.value, {
      content: form.content || undefined,
      files: files.length > 0 ? files : undefined,
      external_order_no: form.external_order_no || undefined,
      customer_remark: form.customer_remark || undefined,
      contact_name: form.contact_name || undefined,
      contact_phone: form.contact_phone || undefined,
      contact_email: form.contact_email || undefined
    })
    submittedRequestNo.value = res.request_no
    successVisible.value = true
    // 重置表单
    form.content = ''
    form.external_order_no = ''
    form.customer_remark = ''
    form.contact_name = ''
    form.contact_phone = ''
    form.contact_email = ''
    fileList.value = []
    // 刷新历史
    fetchHistory()
  } catch {
    // ignore
  } finally {
    submitting.value = false
  }
}

async function fetchHistory() {
  try {
    const res = await getSubmissionHistory(token.value, { page: 1, page_size: 5 })
    historyList.value = res.items
  } catch {
    // ignore
  }
}

async function handleQueryStatus() {
  if (!queryRequestId.value.trim()) {
    ElMessage.warning('请输入申请单号')
    return
  }
  querying.value = true
  queryResult.value = null
  try {
    queryResult.value = await getSubmissionStatus(token.value, queryRequestId.value.trim())
  } catch {
    // ignore
  } finally {
    querying.value = false
  }
}

function goToStatus() {
  successVisible.value = false
  queryRequestId.value = submittedRequestNo.value
  activeTab.value = 'status'
  handleQueryStatus()
}

function downloadFile(url: string, name: string) {
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

onMounted(() => {
  fetchInfo()
  fetchHistory()
})
</script>

<style scoped lang="scss">
.customer-submit-page {
  min-height: 100vh;
  background: #f6f8fb;
  display: flex;
  justify-content: center;
  padding: 40px 20px;
}

.submit-container {
  width: 100%;
  max-width: 720px;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.submit-header {
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

.submit-body {
  padding: 32px 40px;
}

.state-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 0;
  color: #6b7280;

  p {
    margin-top: 16px;
  }
}

.auth-block {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.auth-card {
  width: 100%;
  max-width: 400px;
  border-radius: 8px;
  text-align: center;

  h3 {
    font-size: 18px;
    color: #1f2937;
    margin-bottom: 8px;
  }

  .auth-tip {
    font-size: 13px;
    color: #6b7280;
    margin-bottom: 20px;
  }

  .auth-btn {
    width: 100%;
    margin-top: 16px;
  }
}

.form-block {
  .enterprise-info {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: #f0f5ff;
    border-radius: 8px;
    margin-bottom: 20px;
    font-size: 14px;
    color: #2563eb;
    font-weight: 500;
  }
}

.submit-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 20px;
  }
}

.submit-form {
  max-width: 600px;
}

.submit-actions {
  display: flex;
  justify-content: center;
  margin-top: 24px;

  .el-button {
    min-width: 200px;
  }
}

.status-query {
  .history-list {
    margin-top: 20px;

    .history-title {
      font-size: 13px;
      color: #6b7280;
      margin-bottom: 10px;
    }

    .history-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      border: 1px solid #e5e7eb;
      border-radius: 6px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        border-color: #2563eb;
        background: #f0f5ff;
      }

      &__no {
        flex: 1;
        font-size: 13px;
        color: #1f2937;
        font-weight: 500;
      }

      &__time {
        font-size: 12px;
        color: #9ca3af;
      }
    }
  }
}

.query-result {
  .result-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;

    h4 {
      font-size: 16px;
      color: #1f2937;
      margin: 0;
    }
  }

  .result-timeline {
    padding-left: 0;

    .timeline-label {
      font-size: 14px;
      color: #1f2937;
      margin: 0;
    }

    .timeline-desc {
      font-size: 12px;
      color: #6b7280;
      margin-top: 4px;
    }
  }

  .result-download {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: #f0fdf4;
    border-radius: 6px;
    margin-top: 16px;

    p {
      font-size: 13px;
      color: #1f2937;
      margin: 0;
    }
  }

  .result-error {
    margin-top: 16px;
  }
}

.success-content {
  text-align: center;
  padding: 20px 0;

  .success-title {
    font-size: 18px;
    color: #1f2937;
    margin: 16px 0 12px;
  }

  .success-no {
    font-size: 15px;
    color: #374151;
    margin-bottom: 8px;

    strong {
      color: #2563eb;
      font-size: 16px;
    }
  }

  .success-tip {
    font-size: 13px;
    color: #6b7280;
  }
}
</style>
