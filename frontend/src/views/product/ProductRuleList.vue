<template>
  <div class="page-container">
    <PageHeader title="商品规则" subtitle="管理商品税收分类与开票规则">
      <template #actions>
        <el-button @click="handleBatchImport">
          <el-icon><Upload /></el-icon>批量导入
        </el-button>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>新建规则
        </el-button>
      </template>
    </PageHeader>

    <SearchForm v-model="searchForm" @search="handleSearch" @reset="handleReset">
      <el-form-item label="企业">
        <el-select v-model="searchForm.enterprise_id" placeholder="全部" clearable filterable style="width: 200px">
          <el-option v-for="e in enterpriseOptions" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="商品名称">
        <el-input v-model="searchForm.keyword" placeholder="请输入商品名称" clearable />
      </el-form-item>
    </SearchForm>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" stripe border empty-text="暂无商品规则，请新建或导入">
        <el-table-column prop="original_name" label="原始商品名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="standard_name" label="标准商品名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="tax_code" label="税收分类编码" width="160" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" width="120" show-overflow-tooltip />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="default_tax_rate" label="税率" width="100">
          <template #default="{ row }">{{ formatTaxRate(row.default_tax_rate) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
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
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑商品规则' : '新建商品规则'" width="640px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="120px">
        <el-form-item label="企业" prop="enterprise_id">
          <el-select v-model="formData.enterprise_id" placeholder="请选择企业" filterable style="width: 100%">
            <el-option v-for="e in enterpriseOptions" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="原始商品名称" prop="original_name">
          <el-input v-model="formData.original_name" placeholder="例如：技术开发费" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input v-model="aliasesInput" type="textarea" :rows="2" placeholder="多个别名用逗号分隔，例如：开发费,系统开发" />
        </el-form-item>
        <el-form-item label="标准商品名称" prop="standard_name">
          <el-input v-model="formData.standard_name" placeholder="例如：信息技术服务*软件开发服务" />
        </el-form-item>
        <el-form-item label="税收分类编码" prop="tax_code">
          <el-input v-model="formData.tax_code" placeholder="例如：30402020100000000" />
        </el-form-item>
        <el-form-item label="默认税率" prop="default_tax_rate">
          <el-input-number v-model="formData.default_tax_rate" :min="0" :max="100" :precision="2" :step="1" />
          <span style="margin-left: 8px">%</span>
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="formData.unit" placeholder="例如：次" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="formData.spec" placeholder="例如：标准版" />
        </el-form-item>
        <el-form-item label="备注模板">
          <el-input v-model="formData.remark_template" type="textarea" :rows="2" placeholder="开票备注模板" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="批量导入商品规则" width="500px">
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
              <div class="el-upload__tip">支持 .xlsx, .xls, .csv 格式，需包含列：原始商品名称, 标准商品名称, 税收分类编码, 税率, 单位, 规格</div>
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
import { ref, reactive, onMounted, watch } from 'vue'
import { Plus, Upload, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  getProductRules,
  createProductRule,
  updateProductRule,
  deleteProductRule,
  batchImportProductRules
} from '@/api/product'
import { getEnterprises } from '@/api/enterprise'
import { formatTaxRate } from '@/utils/format'
import type { ProductRule, Enterprise } from '@/types'

const loading = ref(false)
const tableData = ref<ProductRule[]>([])
const enterpriseOptions = ref<Enterprise[]>([])
const searchForm = reactive({ enterprise_id: '', keyword: '' })

const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const dialogVisible = ref(false)
const editingId = ref('')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const aliasesInput = ref('')

const importDialogVisible = ref(false)
const importing = ref(false)
const importEnterpriseId = ref('')
const uploadFile = ref<File | null>(null)

const formData = reactive({
  enterprise_id: '',
  original_name: '',
  standard_name: '',
  tax_code: '',
  default_tax_rate: 13 as number,
  unit: '',
  spec: '',
  remark_template: ''
})

const formRules: FormRules = {
  enterprise_id: [{ required: true, message: '请选择企业', trigger: 'change' }],
  original_name: [{ required: true, message: '请输入原始商品名称', trigger: 'blur' }],
  standard_name: [{ required: true, message: '请输入标准商品名称', trigger: 'blur' }],
  default_tax_rate: [{ required: true, message: '请输入税率', trigger: 'blur' }]
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
    const res = await getProductRules({
      page: pagination.page,
      page_size: pagination.page_size,
      enterprise_id: searchForm.enterprise_id || undefined,
      keyword: searchForm.keyword || undefined
    })
    tableData.value = res.items
    pagination.total = res.total
  } catch (e: any) {
    ElMessage.error(e?.message || '加载商品规则失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  fetchData()
}

function handleReset() {
  searchForm.enterprise_id = ''
  searchForm.keyword = ''
  pagination.page = 1
  fetchData()
}

function handleCreate() {
  editingId.value = ''
  aliasesInput.value = ''
  Object.assign(formData, {
    enterprise_id: '',
    original_name: '',
    standard_name: '',
    tax_code: '',
    default_tax_rate: 13,
    unit: '',
    spec: '',
    remark_template: ''
  })
  dialogVisible.value = true
}

function handleEdit(row: ProductRule) {
  editingId.value = row.id
  aliasesInput.value = (row.aliases || []).join(', ')
  Object.assign(formData, {
    enterprise_id: row.enterprise_id,
    original_name: row.original_name,
    standard_name: row.standard_name,
    tax_code: row.tax_code || '',
    default_tax_rate: row.default_tax_rate ? Number(row.default_tax_rate) : 13,
    unit: row.unit || '',
    spec: row.spec || '',
    remark_template: row.remark_template || ''
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      // 税率由后端需要百分数(13)转为 Decimal(0.13)
      const payload: any = {
        ...formData,
        default_tax_rate: formData.default_tax_rate, // 后端按百分数存储
        aliases: aliasesInput.value
          ? aliasesInput.value.split(/[,，\s]+/).filter(s => s.trim())
          : []
      }
      if (editingId.value) {
        await updateProductRule(editingId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await createProductRule(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } catch (e: any) {
      ElMessage.error(e?.message || '保存失败')
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: ProductRule) {
  try {
    await ElMessageBox.confirm(
      `确定要删除商品规则「${row.original_name}」吗？`,
      '提示',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteProductRule(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // 用户取消
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
    const res = await batchImportProductRules(importEnterpriseId.value, uploadFile.value)
    ElMessage.success(`导入完成：成功 ${res.success}，失败 ${res.failure}`)
    if (res.errors?.length) {
      console.warn('导入错误：', res.errors)
    }
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
