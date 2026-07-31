<template>
  <div class="page-container">
    <PageHeader title="提交链接管理" subtitle="管理客户开票资料提交链接">
      <template #actions>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>创建链接
        </el-button>
      </template>
    </PageHeader>

    <SearchForm v-model="searchForm" @search="handleSearch" @reset="handleReset">
      <el-form-item label="企业">
        <el-select v-model="searchForm.enterprise_id" placeholder="全部企业" clearable filterable style="width: 200px">
          <el-option v-for="e in enterpriseOptions" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
      </el-form-item>
    </SearchForm>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" stripe border>
        <el-table-column prop="enterprise_name" label="企业" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.enterprise_name || getEnterpriseName(row.enterprise_id) }}</template>
        </el-table-column>
        <el-table-column label="链接类型" width="100">
          <template #default="{ row }">
            <el-tag :type="linkTypeTagType(row.link_type)" size="small">{{ linkTypeText(row.link_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Token" min-width="200">
          <template #default="{ row }">
            <div class="token-cell">
              <span class="token-text">{{ truncateToken(row.token) }}</span>
              <el-button link type="primary" size="small" @click="copyToken(row.token)">
                <el-icon><CopyDocument /></el-icon>
              </el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="使用次数" width="120" align="center">
          <template #default="{ row }">
            <span>{{ row.used_count }} / {{ row.max_uses || '∞' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="有效期" width="170">
          <template #default="{ row }">
            {{ row.expires_at ? formatDateTime(row.expires_at) : '永久' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="120">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openLink(row)">打开</el-button>
            <el-button link type="warning" size="small" @click="handleRegenerate(row)">重新生成</el-button>
            <el-button link type="danger" size="small" @click="handleDeactivate(row)">停用</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <!-- 创建链接弹窗 -->
    <el-dialog v-model="dialogVisible" title="创建提交链接" width="500px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="120px">
        <el-form-item label="企业" prop="enterprise_id">
          <el-select v-model="formData.enterprise_id" placeholder="请选择企业" filterable style="width: 100%">
            <el-option v-for="e in enterpriseOptions" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="链接类型" prop="link_type">
          <el-radio-group v-model="formData.link_type">
            <el-radio value="one_time">一次性</el-radio>
            <el-radio value="permanent">永久</el-radio>
            <el-radio value="expiring">限时</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="formData.link_type === 'expiring'" label="有效期至" prop="expires_at">
          <el-date-picker
            v-model="formData.expires_at"
            type="datetime"
            placeholder="选择过期时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="最大使用次数" prop="max_uses">
          <el-input-number v-model="formData.max_uses" :min="1" :max="10000" placeholder="留空表示不限" style="width: 100%" />
        </el-form-item>
        <el-form-item label="访问密码" prop="password">
          <el-input v-model="formData.password" placeholder="留空表示无需密码" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">创建</el-button>
      </template>
    </el-dialog>

    <!-- 创建成功弹窗 -->
    <el-dialog v-model="successVisible" title="链接创建成功" width="480px">
      <div class="success-content">
        <el-icon :size="40" color="#10B981"><CircleCheckFilled /></el-icon>
        <p class="success-tip">提交链接已生成，请复制并发送给客户</p>
        <div class="link-box">
          <span>{{ generatedLink }}</span>
          <el-button type="primary" size="small" @click="copyLink">复制</el-button>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="successVisible = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus, CopyDocument, CircleCheckFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import { getSubmissionLinks, createSubmissionLink, deactivateLink, regenerateToken } from '@/api/submission_links'
import { getEnterprises } from '@/api/enterprise'
import { formatDate, formatDateTime } from '@/utils/format'
import type { Enterprise, SubmissionLink } from '@/types'

const loading = ref(false)
const tableData = ref<SubmissionLink[]>([])
const enterpriseOptions = ref<Enterprise[]>([])
const searchForm = reactive({ enterprise_id: '' })

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const successVisible = ref(false)
const generatedLink = ref('')

const formData = reactive({
  enterprise_id: '',
  link_type: 'one_time' as 'one_time' | 'permanent' | 'expiring',
  expires_at: '',
  max_uses: 1,
  password: ''
})

const formRules: FormRules = {
  enterprise_id: [{ required: true, message: '请选择企业', trigger: 'change' }],
  link_type: [{ required: true, message: '请选择链接类型', trigger: 'change' }],
  expires_at: [{ required: true, message: '请选择有效期', trigger: 'change' }]
}

function getEnterpriseName(id: string) {
  return enterpriseOptions.value.find((e) => e.id === id)?.name || id
}

function linkTypeText(type: string) {
  const map: Record<string, string> = { one_time: '一次性', permanent: '永久', expiring: '限时' }
  return map[type] || type
}

function linkTypeTagType(type: string): 'primary' | 'success' | 'warning' {
  const map: Record<string, 'primary' | 'success' | 'warning'> = {
    one_time: 'warning',
    permanent: 'success',
    expiring: 'primary'
  }
  return map[type] || 'primary'
}

function truncateToken(token: string) {
  if (!token) return ''
  if (token.length <= 16) return token
  return token.substring(0, 8) + '****' + token.substring(token.length - 8)
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getSubmissionLinks({
      enterprise_id: searchForm.enterprise_id || undefined,
      page: pagination.page,
      page_size: pagination.page_size
    })
    tableData.value = res.items
    pagination.total = res.total
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function fetchEnterprises() {
  try {
    const res = await getEnterprises({ page: 1, page_size: 100 })
    enterpriseOptions.value = res.items
  } catch {
    // ignore
  }
}

function handleSearch() {
  pagination.page = 1
  fetchData()
}

function handleReset() {
  pagination.page = 1
  fetchData()
}

function handleCreate() {
  Object.assign(formData, {
    enterprise_id: '',
    link_type: 'one_time',
    expires_at: '',
    max_uses: 1,
    password: ''
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const res = await createSubmissionLink({
        enterprise_id: formData.enterprise_id,
        link_type: formData.link_type,
        password: formData.password || undefined,
        max_uses: formData.max_uses || undefined,
        expires_at: formData.expires_at || undefined
      })
      generatedLink.value = `${window.location.origin}/submit/${res.token}`
      dialogVisible.value = false
      successVisible.value = true
      fetchData()
    } catch {
      // ignore
    } finally {
      submitting.value = false
    }
  })
}

function openLink(row: SubmissionLink) {
  const url = `${window.location.origin}/submit/${row.token}`
  window.open(url, '_blank')
}

async function handleRegenerate(row: SubmissionLink) {
  try {
    await ElMessageBox.confirm('重新生成 Token 后，原链接将立即失效。确定继续吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const res = await regenerateToken(row.id)
    ElMessage.success('Token 已重新生成')
    generatedLink.value = `${window.location.origin}/submit/${res.token}`
    successVisible.value = true
    fetchData()
  } catch {
    // ignore
  }
}

async function handleDeactivate(row: SubmissionLink) {
  try {
    await ElMessageBox.confirm('停用后该链接将无法访问，确定停用吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deactivateLink(row.id)
    ElMessage.success('链接已停用')
    fetchData()
  } catch {
    // ignore
  }
}

function copyToken(token: string) {
  navigator.clipboard.writeText(token).then(() => {
    ElMessage.success('Token 已复制')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

function copyLink() {
  navigator.clipboard.writeText(generatedLink.value).then(() => {
    ElMessage.success('链接已复制')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
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

.token-cell {
  display: flex;
  align-items: center;
  gap: 4px;

  .token-text {
    font-family: 'Courier New', monospace;
    font-size: 12px;
    color: #6b7280;
  }
}

.success-content {
  text-align: center;
  padding: 16px 0;

  .success-tip {
    font-size: 14px;
    color: #374151;
    margin: 12px 0 16px;
  }

  .link-box {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    background: #f6f8fb;
    border-radius: 6px;
    border: 1px solid #e5e7eb;

    span {
      flex: 1;
      font-size: 13px;
      color: #2563eb;
      word-break: break-all;
      font-family: 'Courier New', monospace;
    }
  }
}
</style>
