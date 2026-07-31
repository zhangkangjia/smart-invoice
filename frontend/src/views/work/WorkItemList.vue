<template>
  <div class="page-container">
    <PageHeader title="我的待办" subtitle="待处理的工作项列表" />

    <SearchForm v-model="searchForm" @search="handleSearch" @reset="handleReset">
      <el-form-item label="类型">
        <el-select v-model="searchForm.type" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="opt in WORK_ITEM_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 140px">
          <el-option label="待处理" value="pending" />
          <el-option label="处理中" value="processing" />
          <el-option label="已解决" value="resolved" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
      </el-form-item>
      <el-form-item label="优先级">
        <el-select v-model="searchForm.priority" placeholder="全部" clearable style="width: 120px">
          <el-option v-for="opt in PRIORITY_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-form-item>
    </SearchForm>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" stripe border>
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <StatusTag :status="row.type" type="work-item" />
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="80">
          <template #default="{ row }">
            <StatusTag :status="row.priority" type="priority" />
          </template>
        </el-table-column>
        <el-table-column prop="enterprise_name" label="企业" width="140" show-overflow-tooltip />
        <el-table-column prop="task_no" label="关联任务" width="130" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">{{ formatWorkItemStatus(row.status) }}</template>
        </el-table-column>
        <el-table-column label="截止时间" width="120">
          <template #default="{ row }">{{ formatDate(row.due_date) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleProcess(row)">处理</el-button>
            <el-button link type="warning" size="small" @click="handleTransfer(row)">转派</el-button>
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

    <!-- 处理弹窗 -->
    <el-dialog v-model="processDialogVisible" title="处理工作项" width="500px">
      <el-form :model="processForm" label-width="80px">
        <el-form-item label="处理结果">
          <el-input v-model="processForm.resolution" type="textarea" :rows="4" placeholder="请输入处理结果" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="processForm.remark" type="textarea" :rows="2" placeholder="备注（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="processDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="processing" @click="submitProcess">提交</el-button>
      </template>
    </el-dialog>

    <!-- 转派弹窗 -->
    <el-dialog v-model="transferDialogVisible" title="转派工作项" width="500px">
      <el-form :model="transferForm" label-width="80px">
        <el-form-item label="转派给" required>
          <el-input v-model="transferForm.assignee_id" placeholder="请输入用户ID" />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="transferForm.reason" type="textarea" :rows="3" placeholder="请输入转派原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="transferring" @click="submitTransfer">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import SearchForm from '@/components/SearchForm.vue'
import { getWorkItems, resolveWorkItem, transferWorkItem } from '@/api/work_item'
import { WORK_ITEM_TYPE_OPTIONS, PRIORITY_OPTIONS } from '@/utils/constants'
import { formatDate } from '@/utils/format'
import type { WorkItem } from '@/types'

const loading = ref(false)
const tableData = ref<WorkItem[]>([])
const searchForm = reactive({ type: '', status: 'pending', priority: '' })

const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const processDialogVisible = ref(false)
const processing = ref(false)
const currentWorkItem = ref<WorkItem | null>(null)
const processForm = reactive({ resolution: '', remark: '' })

const transferDialogVisible = ref(false)
const transferring = ref(false)
const transferForm = reactive({ assignee_id: '', reason: '' })

function formatWorkItemStatus(status: string) {
  const map: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    resolved: '已解决',
    cancelled: '已取消'
  }
  return map[status] || status
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getWorkItems({
      page: pagination.page,
      page_size: pagination.page_size,
      type: searchForm.type || undefined,
      status: searchForm.status || undefined,
      priority: searchForm.priority || undefined
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
  searchForm.status = 'pending'
  fetchData()
}

function handleProcess(row: WorkItem) {
  currentWorkItem.value = row
  processForm.resolution = ''
  processForm.remark = ''
  processDialogVisible.value = true
}

async function submitProcess() {
  if (!currentWorkItem.value) return
  if (!processForm.resolution.trim()) {
    ElMessage.warning('请输入处理结果')
    return
  }
  processing.value = true
  try {
    await resolveWorkItem(currentWorkItem.value.id, { ...processForm })
    ElMessage.success('处理成功')
    processDialogVisible.value = false
    fetchData()
  } catch {
    // ignore
  } finally {
    processing.value = false
  }
}

function handleTransfer(row: WorkItem) {
  currentWorkItem.value = row
  transferForm.assignee_id = ''
  transferForm.reason = ''
  transferDialogVisible.value = true
}

async function submitTransfer() {
  if (!currentWorkItem.value) return
  if (!transferForm.assignee_id.trim()) {
    ElMessage.warning('请输入转派对象')
    return
  }
  transferring.value = true
  try {
    await transferWorkItem(currentWorkItem.value.id, transferForm.assignee_id, transferForm.reason)
    ElMessage.success('转派成功')
    transferDialogVisible.value = false
    fetchData()
  } catch {
    // ignore
  } finally {
    transferring.value = false
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
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
