<template>
  <div class="page-container">
    <PageHeader title="机构管理" subtitle="管理组织架构：机构、分公司、部门、团队">
      <template #actions>
        <el-button type="primary" @click="handleCreate('agency')">
          <el-icon><Plus /></el-icon>新建机构
        </el-button>
      </template>
    </PageHeader>

    <el-card v-loading="loading" shadow="never" class="tree-card">
      <el-table :data="treeData" row-key="id" border default-expand-all :tree-props="{ children: 'children' }">
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column prop="code" label="编码" width="150" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeTagType(row._type)" size="small">{{ getTypeText(row._type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="manager_name" label="负责人" width="120" />
        <el-table-column label="创建时间" width="120">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleCreateSub(row)">新建下级</el-button>
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="formData.code" placeholder="请输入编码" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="formData.manager_name" placeholder="请输入负责人" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { getAgencies, createAgency, getBranches, createBranch, getDepartments, getTeams } from '@/api/organization'
import { formatDate } from '@/utils/format'
import type { Agency, Branch, Department, Team } from '@/types'

interface TreeNode extends Record<string, any> {
  id: string
  name: string
  code: string
  manager_name: string
  created_at: string
  _type: string
  children?: TreeNode[]
}

const loading = ref(false)
const treeData = ref<TreeNode[]>([])

const dialogVisible = ref(false)
const dialogType = ref<'agency' | 'branch' | 'department' | 'team'>('agency')
const parentId = ref('')
const formRef = ref<FormInstance>()

const formData = reactive({
  name: '',
  code: '',
  manager_name: ''
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }]
}

const dialogTitle = computed(() => {
  const map = { agency: '机构', branch: '分公司', department: '部门', team: '团队' }
  return `${dialogType.value === 'agency' && !parentId.value ? '新建' : '编辑'}${map[dialogType.value]}`
})

function getTypeText(type: string) {
  const map: Record<string, string> = { agency: '机构', branch: '分公司', department: '部门', team: '团队' }
  return map[type] || type
}

function getTypeTagType(type: string): 'primary' | 'success' | 'warning' | 'info' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info'> = {
    agency: 'primary',
    branch: 'success',
    department: 'warning',
    team: 'info'
  }
  return map[type] || 'info'
}

async function fetchData() {
  loading.value = true
  try {
    const agencies = await getAgencies()
    const tree: TreeNode[] = []

    for (const agency of agencies) {
      const agencyNode: TreeNode = { ...agency, _type: 'agency', children: [] }
      const branches = await getBranches(agency.id)
      for (const branch of branches) {
        const branchNode: TreeNode = { ...branch, _type: 'branch', children: [] }
        const departments = await getDepartments(branch.id)
        for (const dept of departments) {
          const deptNode: TreeNode = { ...dept, _type: 'department', children: [] }
          const teams = await getTeams(dept.id)
          for (const team of teams) {
            deptNode.children!.push({ ...team, _type: 'team' })
          }
          branchNode.children!.push(deptNode)
        }
        agencyNode.children!.push(branchNode)
      }
      tree.push(agencyNode)
    }
    treeData.value = tree
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

function handleCreate(type: 'agency' | 'branch' | 'department' | 'team') {
  dialogType.value = type
  parentId.value = ''
  formData.name = ''
  formData.code = ''
  formData.manager_name = ''
  dialogVisible.value = true
}

function handleCreateSub(row: TreeNode) {
  const typeMap: Record<string, 'agency' | 'branch' | 'department' | 'team'> = {
    agency: 'branch',
    branch: 'department',
    department: 'team'
  }
  const nextType = typeMap[row._type]
  if (!nextType) {
    ElMessage.info('团队已是最低层级')
    return
  }
  dialogType.value = nextType
  parentId.value = row.id
  formData.name = ''
  formData.code = ''
  formData.manager_name = ''
  dialogVisible.value = true
}

function handleEdit(row: TreeNode) {
  dialogType.value = row._type as any
  parentId.value = ''
  formData.name = row.name
  formData.code = row.code
  formData.manager_name = row.manager_name
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      if (dialogType.value === 'agency') {
        await createAgency({ name: formData.name, code: formData.code, manager_name: formData.manager_name })
      } else if (dialogType.value === 'branch') {
        await createBranch({ name: formData.name, code: formData.code, agency_id: parentId.value, manager_name: formData.manager_name })
      }
      ElMessage.success('创建成功')
      dialogVisible.value = false
      fetchData()
    } catch {
      // ignore
    }
  })
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped lang="scss">
.tree-card {
  border-radius: 8px;
}
</style>
