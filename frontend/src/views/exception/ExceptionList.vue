<template>
  <div class="page-container">
    <PageHeader title="异常中心" subtitle="查看和处理系统异常" />

    <!-- 按异常类型分组 -->
    <el-row :gutter="16" class="exception-summary">
      <el-col :span="4" v-for="item in exceptionGroups" :key="item.type">
        <el-card shadow="never" class="summary-card" :class="{ active: selectedType === item.type }" @click="selectType(item.type)">
          <div class="summary-icon" :style="{ background: item.color }">
            <el-icon :size="20" color="#fff"><Warning /></el-icon>
          </div>
          <p class="summary-label">{{ item.label }}</p>
          <p class="summary-count">{{ item.count }}</p>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="table-card">
      <div class="table-header">
        <span>异常列表{{ selectedType ? ` - ${getExceptionTypeText(selectedType)}` : '' }}</span>
        <div>
          <el-button type="primary" :disabled="selectedItems.length === 0" @click="handleBatchFix">
            <el-icon><MagicStick /></el-icon>批量修复 ({{ selectedItems.length }})
          </el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="tableData" stripe border @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="50" />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <StatusTag :status="row.type" type="exception" />
          </template>
        </el-table-column>
        <el-table-column label="严重程度" width="100">
          <template #default="{ row }">
            <StatusTag :status="row.severity" type="priority" />
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="enterprise_name" label="企业" width="140" show-overflow-tooltip />
        <el-table-column prop="task_no" label="关联任务" width="130" show-overflow-tooltip />
        <el-table-column prop="recommendation" label="推荐处理方式" min-width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">{{ formatExceptionStatus(row.status) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="120">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleResolve(row)">处理</el-button>
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
    <el-dialog v-model="resolveDialogVisible" title="处理异常" width="500px">
      <el-form :model="resolveForm" label-width="80px">
        <el-form-item label="处理方案" required>
          <el-input v-model="resolveForm.resolution" type="textarea" :rows="4" placeholder="请输入处理方案" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="resolveForm.remark" type="textarea" :rows="2" placeholder="备注（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resolving" @click="submitResolve">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Warning, MagicStick } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { getExceptions, resolveException, batchFixExceptions } from '@/api/exception'
import { EXCEPTION_TYPE_OPTIONS } from '@/utils/constants'
import { formatDate } from '@/utils/format'
import type { ExceptionCase } from '@/types'

const loading = ref(false)
const tableData = ref<ExceptionCase[]>([])
const selectedType = ref('')
const selectedItems = ref<ExceptionCase[]>([])

const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const resolveDialogVisible = ref(false)
const resolving = ref(false)
const currentException = ref<ExceptionCase | null>(null)
const resolveForm = reactive({ resolution: '', remark: '' })

const exceptionGroups = ref(
  EXCEPTION_TYPE_OPTIONS.map((opt) => ({
    type: opt.value as string,
    label: opt.label,
    color: opt.color || '#909399',
    count: 0
  }))
)

function getExceptionTypeText(type: string) {
  return EXCEPTION_TYPE_OPTIONS.find((o) => o.value === type)?.label || type
}

function formatExceptionStatus(status: string) {
  const map: Record<string, string> = {
    open: '待处理',
    processing: '处理中',
    resolved: '已解决',
    ignored: '已忽略'
  }
  return map[status] || status
}

function selectType(type: string) {
  selectedType.value = selectedType.value === type ? '' : type
  pagination.page = 1
  fetchData()
}

function handleSelectionChange(items: ExceptionCase[]) {
  selectedItems.value = items
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getExceptions({
      page: pagination.page,
      page_size: pagination.page_size,
      type: selectedType.value || undefined,
      status: 'open'
    })
    tableData.value = res.items
    pagination.total = res.total
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function fetchExceptionCounts() {
  for (const group of exceptionGroups.value) {
    try {
      const res = await getExceptions({ page: 1, page_size: 1, type: group.type, status: 'open' })
      group.count = res.total
    } catch {
      // ignore
    }
  }
}

function handleResolve(row: ExceptionCase) {
  currentException.value = row
  resolveForm.resolution = row.recommendation || ''
  resolveForm.remark = ''
  resolveDialogVisible.value = true
}

async function submitResolve() {
  if (!currentException.value) return
  if (!resolveForm.resolution.trim()) {
    ElMessage.warning('请输入处理方案')
    return
  }
  resolving.value = true
  try {
    await resolveException(currentException.value.id, { ...resolveForm })
    ElMessage.success('处理成功')
    resolveDialogVisible.value = false
    fetchData()
    fetchExceptionCounts()
  } catch {
    // ignore
  } finally {
    resolving.value = false
  }
}

async function handleBatchFix() {
  if (selectedItems.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定要批量修复 ${selectedItems.value.length} 条异常吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const ids = selectedItems.value.map((item) => item.id)
    await batchFixExceptions(ids, 'auto')
    ElMessage.success('批量修复已提交')
    fetchData()
    fetchExceptionCounts()
  } catch {
    // ignore
  }
}

onMounted(() => {
  fetchData()
  fetchExceptionCounts()
})
</script>

<style scoped lang="scss">
.exception-summary {
  margin-bottom: 16px;
}

.summary-card {
  border-radius: 8px;
  cursor: pointer;
  text-align: center;
  transition: all 0.2s;

  &:hover {
    border-color: #2563eb;
  }

  &.active {
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
  }

  .summary-icon {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 8px;
  }

  .summary-label {
    font-size: 13px;
    color: #6b7280;
    margin: 0;
  }

  .summary-count {
    font-size: 22px;
    font-weight: 600;
    color: #1f2937;
    margin: 4px 0 0 0;
  }
}

.table-card {
  border-radius: 8px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 600;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
