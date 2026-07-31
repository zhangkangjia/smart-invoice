<template>
  <div class="page-container">
    <PageHeader title="企业列表" subtitle="管理所有接入企业">
      <template #actions>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>新建企业
        </el-button>
      </template>
    </PageHeader>

    <SearchForm v-model="searchForm" @search="handleSearch" @reset="handleReset">
      <el-form-item label="企业名称">
        <el-input v-model="searchForm.name" placeholder="请输入企业名称" clearable />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="opt in ENTERPRISE_STATUS_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-form-item>
    </SearchForm>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" stripe border empty-text="暂无企业，请新建">
        <el-table-column prop="name" label="企业名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="tax_no" label="税号" width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <StatusTag :status="row.status" type="enterprise" />
          </template>
        </el-table-column>
        <el-table-column label="服务等级" width="90">
          <template #default="{ row }">
            {{ getServiceLevelText(row.service_level) }}
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="电话" width="120" show-overflow-tooltip />
        <el-table-column label="创建时间" width="120">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleView(row)">查看</el-button>
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-dropdown trigger="click" @command="(cmd: string) => handleStatusChange(row, cmd)">
              <el-button link type="primary" size="small">状态<el-icon><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="opt in ENTERPRISE_STATUS_OPTIONS" :key="opt.value" :command="opt.value">
                    {{ opt.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
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

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑企业' : '新建企业'" width="600px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="企业名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入企业名称" />
        </el-form-item>
        <el-form-item label="税号" prop="tax_no">
          <div style="display: flex; gap: 8px; width: 100%">
            <el-input v-model="formData.tax_no" placeholder="请输入纳税人识别号" style="flex: 1" />
            <el-button type="primary" plain :loading="lookingUp" @click="handleLookupByTaxNo">
              <el-icon><Search /></el-icon>查询
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="服务等级">
          <el-select v-model="formData.service_level" placeholder="请选择" style="width: 100%">
            <el-option v-for="opt in SERVICE_LEVEL_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="formData.address" placeholder="请输入地址" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="formData.phone" placeholder="请输入电话" />
        </el-form-item>
        <el-form-item label="开户银行">
          <el-input v-model="formData.bank_name" placeholder="请输入开户银行" />
        </el-form-item>
        <el-form-item label="银行账号">
          <el-input v-model="formData.bank_account" placeholder="请输入银行账号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, ArrowDown, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import SearchForm from '@/components/SearchForm.vue'
import { getEnterprises, createEnterprise, updateEnterprise, updateEnterpriseStatus, lookupByTaxNo } from '@/api/enterprise'
import { ENTERPRISE_STATUS_OPTIONS, SERVICE_LEVEL_OPTIONS } from '@/utils/constants'
import { formatDate } from '@/utils/format'
import type { Enterprise } from '@/types'

const router = useRouter()

const loading = ref(false)
const tableData = ref<Enterprise[]>([])
const searchForm = reactive({ name: '', status: '' as string })

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const dialogVisible = ref(false)
const editingId = ref('')
const submitting = ref(false)
const lookingUp = ref(false)
const formRef = ref<FormInstance>()

const formData = reactive({
  name: '',
  tax_no: '',
  service_level: 'normal',
  address: '',
  phone: '',
  bank_name: '',
  bank_account: ''
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入企业名称', trigger: 'blur' }],
  tax_no: [{ required: true, message: '请输入税号', trigger: 'blur' }]
}

function getServiceLevelText(level: string | null) {
  if (!level) return '-'
  return SERVICE_LEVEL_OPTIONS.find((o) => o.value === level)?.label || level
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getEnterprises({
      page: pagination.page,
      page_size: pagination.page_size,
      name: searchForm.name || undefined,
      status: searchForm.status || undefined
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
  fetchData()
}

function handleView(row: Enterprise) {
  router.push(`/enterprises/${row.id}`)
}

function handleCreate() {
  editingId.value = ''
  Object.assign(formData, {
    name: '', tax_no: '', service_level: 'normal',
    address: '', phone: '', bank_name: '', bank_account: ''
  })
  dialogVisible.value = true
}

async function handleLookupByTaxNo() {
  if (!formData.tax_no || formData.tax_no.trim().length < 6) {
    ElMessage.warning('请输入完整的税号')
    return
  }
  lookingUp.value = true
  try {
    const res = await lookupByTaxNo(formData.tax_no.trim())
    if (res.found_locally && res.enterprise) {
      // 本地已存在
      ElMessage.info(res.message)
      Object.assign(formData, {
        name: res.enterprise.name,
        tax_no: res.enterprise.tax_no || '',
        service_level: res.enterprise.service_level || 'normal',
        address: res.enterprise.address || '',
        phone: res.enterprise.phone || '',
        bank_name: res.enterprise.bank_name || '',
        bank_account: res.enterprise.bank_account || ''
      })
    } else if (res.found_remote && res.suggestion) {
      // 百望云获取到信息
      const s = res.suggestion
      if (s.name) formData.name = s.name
      if (s.address) formData.address = s.address
      if (s.phone) formData.phone = s.phone
      if (s.bank_name) formData.bank_name = s.bank_name
      if (s.bank_account) formData.bank_account = s.bank_account
      ElMessage.success(res.message)
    } else {
      ElMessage.info(res.message)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '查询失败')
  } finally {
    lookingUp.value = false
  }
}

function handleEdit(row: Enterprise) {
  editingId.value = row.id
  Object.assign(formData, {
    name: row.name,
    tax_no: row.tax_no || '',
    service_level: row.service_level || 'normal',
    address: row.address || '',
    phone: row.phone || '',
    bank_name: row.bank_name || '',
    bank_account: row.bank_account || ''
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (editingId.value) {
        await updateEnterprise(editingId.value, { ...formData })
        ElMessage.success('更新成功')
      } else {
        await createEnterprise({ ...formData, status: 'pending' })
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } catch {
      // ignore
    } finally {
      submitting.value = false
    }
  })
}

async function handleStatusChange(row: Enterprise, status: string) {
  try {
    await ElMessageBox.confirm(
      `确定要将企业「${row.name}」状态变更为「${formatStatusText(status)}」吗？`,
      '提示',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await updateEnterpriseStatus(row.id, status)
    ElMessage.success('状态变更成功')
    fetchData()
  } catch {
    // ignore
  }
}

function formatStatusText(status: string) {
  return ENTERPRISE_STATUS_OPTIONS.find((o) => o.value === status)?.label || status
}

onMounted(() => {
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
