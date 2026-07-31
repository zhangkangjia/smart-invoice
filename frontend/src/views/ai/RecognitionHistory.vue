<template>
  <div class="page-container">
    <PageHeader title="识别记录" subtitle="查看 AI 识别历史记录与详情" />

    <SearchForm v-model="searchForm" @search="handleSearch" @reset="handleReset">
      <el-form-item label="来源类型">
        <el-select v-model="searchForm.source_type" placeholder="全部" clearable style="width: 140px">
          <el-option label="文字识别" value="text" />
          <el-option label="图片识别" value="image" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期范围">
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
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="来源类型" width="110">
          <template #default="{ row }">
            <el-tag :type="row.source_type === 'text' ? 'primary' : 'success'" size="small">
              {{ row.source_type === 'text' ? '文字识别' : '图片识别' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enterprise_name" label="企业" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'warning'" size="small">
              {{ row.status === 'success' ? '成功' : '部分成功' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="field_count" label="字段数" width="90" align="center" />
        <el-table-column label="平均置信度" width="140" align="center">
          <template #default="{ row }">
            <div class="confidence-cell">
              <el-progress
                :percentage="Math.round(row.avg_confidence * 100)"
                :color="confidenceColor(row.avg_confidence)"
                :stroke-width="8"
                :show-text="false"
                style="width: 80px"
              />
              <span :style="{ color: confidenceColor(row.avg_confidence) }">{{ (row.avg_confidence * 100).toFixed(1) }}%</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleViewDetail(row)">查看详情</el-button>
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

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="识别详情" width="700px" top="5vh">
      <div v-loading="detailLoading">
        <div v-if="detailData" class="detail-content">
          <el-descriptions :column="2" border size="small" class="detail-desc">
            <el-descriptions-item label="模型">{{ detailData.model_name }} v{{ detailData.model_version }}</el-descriptions-item>
            <el-descriptions-item label="处理耗时">{{ detailData.processing_time_ms }}ms</el-descriptions-item>
            <el-descriptions-item label="来源类型">{{ detailData.source_type === 'text' ? '文字识别' : '图片识别' }}</el-descriptions-item>
            <el-descriptions-item label="识别时间">{{ formatDateTime(detailData.created_at) }}</el-descriptions-item>
          </el-descriptions>

          <div v-if="detailData.errors.length" class="detail-errors">
            <el-alert
              v-for="(err, idx) in detailData.errors"
              :key="idx"
              :title="err"
              type="warning"
              :closable="false"
              show-icon
            />
          </div>

          <el-table :data="detailData.fields" stripe size="small" class="detail-table">
            <el-table-column label="字段名" min-width="120">
              <template #default="{ row }">{{ fieldDisplayName(row.field_name) }}</template>
            </el-table-column>
            <el-table-column label="识别值" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.value }}</template>
            </el-table-column>
            <el-table-column label="来源" width="90">
              <template #default="{ row }">{{ sourceDisplayName(row.source) }}</template>
            </el-table-column>
            <el-table-column label="置信度" width="140" align="center">
              <template #default="{ row }">
                <div class="confidence-cell">
                  <el-progress
                    :percentage="Math.round(row.confidence * 100)"
                    :color="confidenceColor(row.confidence)"
                    :stroke-width="8"
                    :show-text="false"
                    style="width: 80px"
                  />
                  <span :style="{ color: confidenceColor(row.confidence) }">{{ (row.confidence * 100).toFixed(1) }}%</span>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import { getRecognitionHistory, getRecognitionDetail, type RecognitionHistoryItem } from '@/api/ai'
import { formatDateTime } from '@/utils/format'
import type { RecognitionResult } from '@/types'

const loading = ref(false)
const tableData = ref<RecognitionHistoryItem[]>([])
const searchForm = reactive({ source_type: '', start_date: '', end_date: '' })
const dateRange = ref<[string, string] | null>(null)

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<(RecognitionResult & { id: string; source_type: string; enterprise_name: string; created_at: string }) | null>(null)

watch(dateRange, (val) => {
  if (val && val.length === 2) {
    searchForm.start_date = val[0]
    searchForm.end_date = val[1]
  } else {
    searchForm.start_date = ''
    searchForm.end_date = ''
  }
})

const FIELD_NAME_MAP: Record<string, string> = {
  buyer_name: '购方名称',
  buyer_tax_number: '购方税号',
  buyer_address: '购方地址',
  buyer_phone: '购方电话',
  buyer_bank_name: '购方开户行',
  buyer_bank_account: '购方账号',
  invoice_type: '发票类型',
  invoice_kind: '发票种类',
  product_name: '商品名称',
  product_spec: '规格型号',
  product_unit: '单位',
  product_quantity: '数量',
  product_unit_price: '单价',
  product_amount: '金额',
  tax_rate: '税率',
  tax_amount: '税额',
  total_amount: '合计金额',
  total_with_tax: '价税合计',
  remark: '备注'
}

const SOURCE_NAME_MAP: Record<string, string> = {
  ocr: 'OCR',
  llm: '大模型',
  multimodal: '多模态',
  rule: '规则',
  knowledge_base: '知识库'
}

function fieldDisplayName(name: string) {
  return FIELD_NAME_MAP[name] || name
}

function sourceDisplayName(source: string) {
  return SOURCE_NAME_MAP[source] || source
}

function confidenceColor(confidence: number) {
  if (confidence >= 0.8) return '#10B981'
  if (confidence >= 0.6) return '#F59E0B'
  return '#EF4444'
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getRecognitionHistory({
      page: pagination.page,
      page_size: pagination.page_size,
      source_type: searchForm.source_type || undefined,
      start_date: searchForm.start_date || undefined,
      end_date: searchForm.end_date || undefined
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
  dateRange.value = null
  pagination.page = 1
  fetchData()
}

async function handleViewDetail(row: RecognitionHistoryItem) {
  detailVisible.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    const res = await getRecognitionDetail(row.id)
    detailData.value = res
  } catch {
    // ignore
  } finally {
    detailLoading.value = false
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

.confidence-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
}

.detail-content {
  .detail-desc {
    margin-bottom: 16px;
  }

  .detail-errors {
    margin-bottom: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .detail-table {
    border-radius: 6px;
  }
}
</style>
