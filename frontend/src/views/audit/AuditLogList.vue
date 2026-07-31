<template>
  <div class="page-container">
    <PageHeader title="审计日志" subtitle="系统操作审计记录" />

    <SearchForm v-model="searchForm" @search="handleSearch" @reset="handleReset">
      <el-form-item label="用户">
        <el-input v-model="searchForm.user_name" placeholder="请输入用户名" clearable />
      </el-form-item>
      <el-form-item label="模块">
        <el-select v-model="searchForm.module" placeholder="全部" clearable style="width: 160px">
          <el-option label="用户管理" value="user" />
          <el-option label="企业管理" value="enterprise" />
          <el-option label="开票管理" value="invoice" />
          <el-option label="任务管理" value="task" />
          <el-option label="系统设置" value="system" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failure" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
        />
      </el-form-item>
    </SearchForm>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" stripe border>
        <el-table-column prop="user_name" label="用户" width="100" />
        <el-table-column prop="module" label="模块" width="120" />
        <el-table-column prop="action" label="操作" width="120" />
        <el-table-column prop="resource_type" label="资源类型" width="120" />
        <el-table-column prop="resource_id" label="资源ID" width="120" show-overflow-tooltip />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP地址" width="130" />
        <el-table-column label="耗时" width="80" align="right">
          <template #default="{ row }">{{ row.duration }}ms</template>
        </el-table-column>
        <el-table-column label="操作时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleViewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" title="日志详情" width="700px">
      <el-descriptions v-if="currentLog" :column="2" border>
        <el-descriptions-item label="用户">{{ currentLog.user_name }}</el-descriptions-item>
        <el-descriptions-item label="模块">{{ currentLog.module }}</el-descriptions-item>
        <el-descriptions-item label="操作">{{ currentLog.action }}</el-descriptions-item>
        <el-descriptions-item label="资源类型">{{ currentLog.resource_type }}</el-descriptions-item>
        <el-descriptions-item label="资源ID">{{ currentLog.resource_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ currentLog.status === 'success' ? '成功' : '失败' }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ currentLog.ip }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ currentLog.duration }}ms</el-descriptions-item>
        <el-descriptions-item label="User-Agent" :span="2">{{ currentLog.user_agent }}</el-descriptions-item>
        <el-descriptions-item label="操作时间" :span="2">{{ formatDateTime(currentLog.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="请求数据" :span="2">
          <pre class="json-content">{{ currentLog.request_data }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="响应数据" :span="2">
          <pre class="json-content">{{ currentLog.response_data }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import { getAuditLogs } from '@/api/audit'
import { formatDateTime } from '@/utils/format'
import type { AuditLog } from '@/types'

const loading = ref(false)
const tableData = ref<AuditLog[]>([])
const dateRange = ref<[string, string] | null>(null)
const searchForm = reactive({ user_name: '', module: '', status: '' })

const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const detailDialogVisible = ref(false)
const currentLog = ref<AuditLog | null>(null)

async function fetchData() {
  loading.value = true
  try {
    const res = await getAuditLogs({
      page: pagination.page,
      page_size: pagination.page_size,
      user_name: searchForm.user_name || undefined,
      module: searchForm.module || undefined,
      status: searchForm.status || undefined,
      start_date: dateRange.value?.[0] || undefined,
      end_date: dateRange.value?.[1] || undefined
    } as any)
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
  dateRange.value = null
  fetchData()
}

function handleViewDetail(row: AuditLog) {
  currentLog.value = row
  detailDialogVisible.value = true
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
.json-content {
  background: #f6f8fb;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
