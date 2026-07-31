<template>
  <div class="page-container">
    <PageHeader title="用户管理" subtitle="管理系统用户和角色">
      <template #actions>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>新建用户
        </el-button>
      </template>
    </PageHeader>

    <SearchForm v-model="searchForm" @search="handleSearch" @reset="handleReset">
      <el-form-item label="用户名">
        <el-input v-model="searchForm.username" placeholder="请输入用户名" clearable />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input v-model="searchForm.full_name" placeholder="请输入姓名" clearable />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px">
          <el-option label="正常" value="active" />
          <el-option label="未激活" value="inactive" />
          <el-option label="已禁用" value="disabled" />
        </el-select>
      </el-form-item>
    </SearchForm>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" stripe border>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="full_name" label="姓名" width="100" />
        <el-table-column prop="email" label="邮箱" width="180" show-overflow-tooltip />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column label="角色" min-width="150">
          <template #default="{ row }">
            <el-tag v-for="role in row.roles" :key="role.id" size="small" style="margin-right: 4px">
              {{ role.name }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="department_name" label="部门" width="120" show-overflow-tooltip />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="150">
          <template #default="{ row }">{{ formatDateTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="primary" size="small" @click="handleAssignRole(row)">角色分配</el-button>
            <el-button link type="danger" size="small" @click="handleToggleStatus(row)">
              {{ row.status === 'active' ? '禁用' : '启用' }}
            </el-button>
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
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑用户' : '新建用户'" width="600px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="formData.username" placeholder="请输入用户名" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="姓名" prop="full_name">
          <el-input v-model="formData.full_name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="formData.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="formData.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item v-if="!editingId" label="密码" prop="password">
          <el-input v-model="formData.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="formData.department_name" placeholder="请输入部门" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 角色分配弹窗 -->
    <el-dialog v-model="roleDialogVisible" title="角色分配" width="500px">
      <el-checkbox-group v-model="selectedRoles">
        <el-checkbox v-for="role in allRoles" :key="role.id" :label="role.id" style="display: block; margin-bottom: 8px">
          {{ role.name }} - {{ role.description }}
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRoles">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import request from '@/api/request'
import { formatDateTime } from '@/utils/format'
import type { User, Role } from '@/types'

const loading = ref(false)
const tableData = ref<User[]>([])
const searchForm = reactive({ username: '', full_name: '', status: '' })

const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const dialogVisible = ref(false)
const editingId = ref('')
const submitting = ref(false)
const formRef = ref<FormInstance>()

const formData = reactive({
  username: '',
  full_name: '',
  email: '',
  phone: '',
  password: '',
  department_name: ''
})

const formRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  full_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const roleDialogVisible = ref(false)
const selectedRoles = ref<string[]>([])
const allRoles = ref<Role[]>([])
const currentUser = ref<User | null>(null)

function getStatusType(status: string): 'success' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'info' | 'danger'> = {
    active: 'success',
    inactive: 'info',
    disabled: 'danger'
  }
  return map[status] || 'info'
}

function getStatusText(status: string) {
  const map: Record<string, string> = { active: '正常', inactive: '未激活', disabled: '已禁用' }
  return map[status] || status
}

async function fetchData() {
  loading.value = true
  try {
    const res = await request.get<unknown, any>('/users', {
      params: {
        page: pagination.page,
        page_size: pagination.page_size,
        username: searchForm.username || undefined,
        full_name: searchForm.full_name || undefined,
        status: searchForm.status || undefined
      }
    })
    tableData.value = res.items
    pagination.total = res.total
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function fetchRoles() {
  try {
    allRoles.value = await request.get<unknown, Role[]>('/roles')
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
  editingId.value = ''
  Object.assign(formData, {
    username: '',
    full_name: '',
    email: '',
    phone: '',
    password: '',
    department_name: ''
  })
  dialogVisible.value = true
}

function handleEdit(row: User) {
  editingId.value = row.id
  Object.assign(formData, {
    username: row.username,
    full_name: row.full_name,
    email: row.email,
    phone: row.phone,
    password: '',
    department_name: row.department_name
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
        await request.put(`/users/${editingId.value}`, { ...formData })
        ElMessage.success('更新成功')
      } else {
        await request.post('/users', { ...formData })
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

function handleAssignRole(row: User) {
  currentUser.value = row
  selectedRoles.value = row.roles.map((r) => r.id)
  roleDialogVisible.value = true
}

async function submitRoles() {
  if (!currentUser.value) return
  try {
    await request.put(`/users/${currentUser.value.id}/roles`, { role_ids: selectedRoles.value })
    ElMessage.success('角色分配成功')
    roleDialogVisible.value = false
    fetchData()
  } catch {
    // ignore
  }
}

async function handleToggleStatus(row: User) {
  const newStatus = row.status === 'active' ? 'disabled' : 'active'
  try {
    await ElMessageBox.confirm(`确定要${newStatus === 'active' ? '启用' : '禁用'}用户「${row.full_name}」吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await request.patch(`/users/${row.id}/status`, { status: newStatus })
    ElMessage.success('操作成功')
    fetchData()
  } catch {
    // ignore
  }
}

onMounted(() => {
  fetchData()
  fetchRoles()
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
