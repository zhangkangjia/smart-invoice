<template>
  <div class="page-container">
    <PageHeader title="客户抬头" subtitle="管理客户开票抬头信息">
      <template #actions>
        <el-button @click="handleBatchImport">
          <el-icon><Upload /></el-icon>批量导入
        </el-button>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>新建抬头
        </el-button>
      </template>
    </PageHeader>

    <SearchForm v-model="searchForm" @search="handleSearch" @reset="handleReset">
      <el-form-item label="企业">
        <el-select v-model="searchForm.enterprise_id" placeholder="全部" clearable filterable style="width: 200px">
          <el-option v-for="e in enterpriseOptions" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="客户名称">
        <el-input v-model="searchForm.name" placeholder="请输入客户名称" clearable />
      </el-form-item>
    </SearchForm>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" stripe border empty-text="暂无客户抬头，请新建或导入">
        <el-table-column prop="name" label="客户名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="tax_no" label="税号" width="200" show-overflow-tooltip />
        <el-table-column prop="address" label="地址" min-width="200" show-overflow-tooltip />
        <el-table-column prop="phone" label="电话" width="130" show-overflow-tooltip />
        <el-table-column prop="bank_name" label="开户行" width="150" show-overflow-tooltip />
        <el-table-column prop="email" label="邮箱" width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
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
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑客户抬头' : '新建客户抬头'" width="600px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="企业" prop="enterprise_id">
          <el-select v-model="formData.enterprise_id" placeholder="请选择企业" filterable style="width: 100%">
            <el-option v-for="e in enterpriseOptions" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入客户名称" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input v-model="formData.alias" placeholder="客户别名（可选）" />
        </el-form-item>
        <el-form-item label="税号" prop="tax_no">
          <div style="display: flex; gap: 8px; width: 100%">
            <el-input v-model="formData.tax_no" placeholder="请输入纳税人识别号" style="flex: 1" />
            <el-button type="primary" plain :loading="lookingUp" @click="handleLookupByTaxNo">
              <el-icon><Search /></el-icon>查询
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="formData.address" placeholder="请输入地址" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="formData.phone" placeholder="请输入电话" />
        </el-form-item>
        <el-form-item label="开户行">
          <el-input v-model="formData.bank_name" placeholder="请输入开户行" />
        </el-form-item>
        <el-form-item label="银行账号">
          <el-input v-model="formData.bank_account" placeholder="请输入银行账号" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="formData.email" placeholder="请输入接收发票邮箱" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="formData.mobile" placeholder="请输入手机号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="批量导入客户抬头" width="500px">
      <el-form label-width="80px">
        <el-form-item label="目标企业">
          <el-select v-model="importEnterpriseId" placeholder="请选择目标企业" filterable style="width: 100%">
            <el-option v-for="e in enterpriseOptions" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择文件">
          <el-upload drag accept=".xlsx,.xls,.csv" :auto-upload="false" :limit="1" :on-change="handleFileChange">
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持 .xlsx, .xls, .csv，需包含：客户名称, 税号, 地址, 电话, 开户行, 银行账号</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImportSubmit">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus, Upload, UploadFilled, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  getCustomerTitles,
  createCustomerTitle,
  updateCustomerTitle,
  deleteCustomerTitle,
  batchImportCustomerTitles,
  lookupCustomerByTaxNo
} from '@/api/customer'
import { getEnterprises } from '@/api/enterprise'
import type { CustomerTitle, Enterprise } from '@/types'

const loading = ref(false)
const tableData = ref<CustomerTitle[]>([])
const enterpriseOptions = ref<Enterprise[]>([])
const searchForm = reactive({ enterprise_id: '', name: '' })

const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const dialogVisible = ref(false)
const editingId = ref('')
const submitting = ref(false)
const lookingUp = ref(false)
const formRef = ref<FormInstance>()

const importDialogVisible = ref(false)
const importing = ref(false)
const importEnterpriseId = ref('')
const uploadFile = ref<File | null>(null)

const formData = reactive({
  enterprise_id: '',
  name: '',
  alias: '',
  tax_no: '',
  address: '',
  phone: '',
  bank_name: '',
  bank_account: '',
  email: '',
  mobile: ''
})

const formRules: FormRules = {
  enterprise_id: [{ required: true, message: '请选择企业', trigger: 'change' }],
  name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }]
}

async function fetchEnterprises() {
  try {
    const res = await getEnterprises({ page: 1, page_size: 100 })
    enterpriseOptions.value = res.items
  } catch {
    enterpriseOptions.value = []
  }
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getCustomerTitles({
      page: pagination.page,
      page_size: pagination.page_size,
      enterprise_id: searchForm.enterprise_id || undefined,
      name: searchForm.name || undefined
    })
    tableData.value = res.items
    pagination.total = res.total
  } catch {
    tableData.value = []
    pagination.total = 0
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

function handleCreate() {
  editingId.value = ''
  Object.assign(formData, {
    enterprise_id: '', name: '', alias: '', tax_no: '',
    address: '', phone: '', bank_name: '', bank_account: '',
    email: '', mobile: ''
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
    const res = await lookupCustomerByTaxNo(formData.tax_no.trim(), formData.enterprise_id || undefined)
    if (res.found_locally && res.customer_title) {
      ElMessage.info(res.message)
      const t = res.customer_title
      formData.name = t.name
      formData.alias = t.alias || ''
      formData.address = t.address || ''
      formData.phone = t.phone || ''
      formData.bank_name = t.bank_name || ''
      formData.bank_account = t.bank_account || ''
      formData.email = t.email || ''
      formData.mobile = t.mobile || ''
    } else if (res.found_remote && res.suggestion) {
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

function handleEdit(row: CustomerTitle) {
  editingId.value = row.id
  Object.assign(formData, {
    enterprise_id: row.enterprise_id,
    name: row.name,
    alias: row.alias || '',
    tax_no: row.tax_no || '',
    address: row.address || '',
    phone: row.phone || '',
    bank_name: row.bank_name || '',
    bank_account: row.bank_account || '',
    email: row.email || '',
    mobile: row.mobile || ''
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
        await updateCustomerTitle(editingId.value, { ...formData })
        ElMessage.success('更新成功')
      } else {
        await createCustomerTitle({ ...formData })
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

async function handleDelete(row: CustomerTitle) {
  try {
    await ElMessageBox.confirm(`确定要删除客户抬头「${row.name}」吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteCustomerTitle(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // ignore
  }
}

function handleBatchImport() {
  uploadFile.value = null
  importEnterpriseId.value = ''
  importDialogVisible.value = true
}

function handleFileChange(file: any) {
  uploadFile.value = file.raw
}

async function handleImportSubmit() {
  if (!importEnterpriseId.value) {
    ElMessage.warning('请选择目标企业')
    return
  }
  if (!uploadFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  importing.value = true
  try {
    await batchImportCustomerTitles(importEnterpriseId.value, uploadFile.value)
    ElMessage.success('导入成功')
    importDialogVisible.value = false
    fetchData()
  } catch (e: any) {
    ElMessage.error(e?.message || '导入失败')
  } finally {
    importing.value = false
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
