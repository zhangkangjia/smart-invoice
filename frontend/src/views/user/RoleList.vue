<template>
  <div class="page-container">
    <PageHeader title="角色管理" subtitle="管理系统角色和权限">
      <template #actions>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>新建角色
        </el-button>
      </template>
    </PageHeader>

    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
      <template #title>
        系统内置 10 个角色（超级管理员/机构管理员/财税主管/开票员等），不可删除但可修改权限。
        可新建自定义角色并分配权限给用户。
      </template>
    </el-alert>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" stripe border>
        <el-table-column prop="name" label="角色名称" width="160" />
        <el-table-column prop="code" label="编码" width="160">
          <template #default="{ row }">
            <el-tag size="small" :type="isBuiltin(row.code) ? 'info' : 'success'">
              {{ row.code }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="权限" min-width="300">
          <template #default="{ row }">
            <el-tag
              v-for="p in (row.permissions || []).slice(0, 5)"
              :key="p"
              size="small"
              type="warning"
              style="margin: 2px"
            >{{ p }}</el-tag>
            <el-tag v-if="(row.permissions || []).length > 5" size="small" style="margin: 2px">
              +{{ row.permissions.length - 5 }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="isBuiltin(row.code) ? 'info' : 'success'" size="small">
              {{ isBuiltin(row.code) ? '内置' : '自定义' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button
              v-if="!isBuiltin(row.code)"
              link type="danger" size="small"
              @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑角色' : '新建角色'" width="640px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="formData.name" placeholder="如：高级开票员" />
        </el-form-item>
        <el-form-item label="角色编码" prop="code">
          <el-input
            v-model="formData.code"
            placeholder="如：senior_clerk（英文/下划线）"
            :disabled="!!editingId"
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" :rows="2" placeholder="角色职责说明" />
        </el-form-item>
        <el-form-item label="权限">
          <div class="perm-section">
            <el-checkbox-group v-model="formData.permissions">
              <div v-for="group in permissionGroups" :key="group.module" class="perm-group">
                <div class="perm-group-title">{{ group.label }}</div>
                <el-checkbox
                  v-for="action in group.actions"
                  :key="`${group.module}.${action}`"
                  :label="`${group.module}.${action}`"
                >{{ action }}</el-checkbox>
              </div>
            </el-checkbox-group>
          </div>
          <div style="margin-top: 8px">
            <el-button link type="primary" @click="selectAll">全选</el-button>
            <el-button link @click="formData.permissions = []">清空</el-button>
          </div>
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
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import request from '@/api/request'

const BUILTIN_CODES = [
  'super_admin', 'agency_admin', 'branch_admin', 'tax_supervisor',
  'accountant', 'invoice_clerk', 'customer_service', 'operator',
  'auditor', 'substitute',
]

function isBuiltin(code: string) {
  return BUILTIN_CODES.includes(code)
}

// 权限模块定义
const permissionGroups = [
  { module: 'enterprise', label: '企业管理', actions: ['read', 'create', 'update', 'delete'] },
  { module: 'customer', label: '客户管理', actions: ['read', 'create', 'update', 'delete'] },
  { module: 'product', label: '商品规则', actions: ['read', 'create', 'update', 'delete'] },
  { module: 'invoice', label: '开票', actions: ['read', 'create', 'update', 'delete'] },
  { module: 'task', label: '任务', actions: ['read', 'create', 'update', 'delete'] },
  { module: 'business', label: '业务申请', actions: ['read', 'create', 'update'] },
  { module: 'exception', label: '异常处理', actions: ['read', 'update'] },
  { module: 'user', label: '用户管理', actions: ['read', 'create', 'update', 'delete'] },
  { module: 'audit', label: '审计日志', actions: ['read'] },
  { module: 'config', label: '系统配置', actions: ['read', 'update'] },
]

function allPermissions(): string[] {
  const all: string[] = []
  for (const g of permissionGroups) {
    for (const a of g.actions) {
      all.push(`${g.module}.${a}`)
    }
  }
  return all
}

function selectAll() {
  formData.permissions = allPermissions()
}

const loading = ref(false)
const tableData = ref<any[]>([])
const dialogVisible = ref(false)
const editingId = ref('')
const submitting = ref(false)
const formRef = ref<FormInstance>()

const formData = reactive({
  name: '',
  code: '',
  description: '',
  permissions: [] as string[],
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  code: [
    { required: true, message: '请输入角色编码', trigger: 'blur' },
    { pattern: /^[a-z_]+$/, message: '只能小写字母和下划线', trigger: 'blur' },
  ],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await request.get<unknown, any>('/users/roles/all')
    tableData.value = res.items
  } catch {
    ElMessage.error('加载角色失败')
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  editingId.value = ''
  Object.assign(formData, { name: '', code: '', description: '', permissions: [] })
  dialogVisible.value = true
}

function handleEdit(row: any) {
  editingId.value = row.id
  Object.assign(formData, {
    name: row.name,
    code: row.code,
    description: row.description || '',
    permissions: [...(row.permissions || [])],
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
        await request.put(`/users/roles/${editingId.value}`, { ...formData })
        ElMessage.success('角色已更新')
      } else {
        await request.post('/users/roles', { ...formData })
        ElMessage.success('角色已创建')
      }
      dialogVisible.value = false
      fetchData()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '操作失败')
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除角色「${row.name}」？`, '删除确认', { type: 'warning' })
    await request.delete(`/users/roles/${row.id}`)
    ElMessage.success('角色已删除')
    fetchData()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped lang="scss">
.table-card {
  border-radius: 8px;
}
.perm-section {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  max-height: 300px;
  overflow-y: auto;
}
.perm-group {
  margin-bottom: 12px;

  &-title {
    font-weight: 600;
    font-size: 13px;
    color: #303133;
    margin-bottom: 6px;
    padding-bottom: 4px;
    border-bottom: 1px solid #f0f0f0;
  }
}
</style>
