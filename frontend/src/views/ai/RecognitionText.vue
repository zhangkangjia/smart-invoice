<template>
  <div class="page-container recognition-text">
    <PageHeader title="文字识别" subtitle="输入开票指令，AI 自动识别发票字段">
      <template #actions>
        <el-button @click="handleClear">清空</el-button>
        <el-button type="primary" :loading="recognizing" :disabled="!canRecognize" @click="handleRecognize">
          <el-icon><Promotion /></el-icon>开始识别
        </el-button>
      </template>
    </PageHeader>

    <el-row :gutter="16" class="main-row">
      <!-- 左侧：输入区 -->
      <el-col :span="12">
        <el-card shadow="never" class="input-card">
          <template #header>
            <div class="card-header">
              <span>开票指令输入</span>
              <el-select v-model="form.enterprise_id" placeholder="选择企业" filterable size="small" style="width: 200px">
                <el-option v-for="e in enterpriseOptions" :key="e.id" :label="e.name" :value="e.id" />
              </el-select>
            </div>
          </template>
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="20"
            placeholder="请输入开票指令，支持多行。例如：&#10;帮开一张电子普通发票给北京科技有限公司，税号91110000XXXXXX，金额10000元，明细：咨询服务费 5000元，技术服务费 5000元"
            resize="none"
          />
          <div class="input-tips">
            <el-icon><InfoFilled /></el-icon>
            <span>支持多行输入，每行可包含一条开票指令。AI 将自动识别购方信息、商品明细、金额等字段。</span>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：识别结果 -->
      <el-col :span="12">
        <el-card shadow="never" class="result-card">
          <template #header>
            <div class="card-header">
              <span>识别结果</span>
              <div class="result-meta" v-if="result">
                <el-tag size="small" type="info">{{ result.model_name }} v{{ result.model_version }}</el-tag>
                <el-tag size="small">{{ result.processing_time_ms }}ms</el-tag>
              </div>
            </div>
          </template>

          <div v-if="recognizing" class="loading-state">
            <el-icon class="is-loading" :size="32" color="#2563EB"><Loading /></el-icon>
            <p>正在识别中...</p>
          </div>

          <div v-else-if="!result" class="empty-state">
            <el-empty description="识别结果将在此显示" />
          </div>

          <div v-else-if="result.fields.length === 0" class="empty-state">
            <el-empty description="未识别到有效字段" />
            <div v-if="result.errors.length" class="error-list">
              <el-alert
                v-for="(err, idx) in result.errors"
                :key="idx"
                :title="err"
                type="error"
                :closable="false"
                show-icon
              />
            </div>
          </div>

          <div v-else class="result-content">
            <el-alert
              v-if="result.errors.length"
              type="warning"
              :closable="false"
              show-icon
              class="warn-alert"
            >
              <template #title>识别过程中存在 {{ result.errors.length }} 个警告</template>
            </el-alert>

            <div class="field-list">
              <div
                v-for="(field, idx) in editableFields"
                :key="idx"
                class="field-item"
                :class="{ 'field-item--low': field.confidence < 0.6 }"
              >
                <div class="field-item__header">
                  <span class="field-item__name">{{ fieldDisplayName(field.field_name) }}</span>
                  <el-tag size="small" :type="sourceTagType(field.source)">{{ sourceDisplayName(field.source) }}</el-tag>
                </div>
                <el-input
                  v-model="field.value"
                  size="default"
                  class="field-item__input"
                />
                <div class="field-item__confidence">
                  <el-progress
                    :percentage="Math.round(field.confidence * 100)"
                    :color="confidenceColor(field.confidence)"
                    :stroke-width="6"
                    :show-text="false"
                  />
                  <span class="confidence-text" :style="{ color: confidenceColor(field.confidence) }">
                    {{ (field.confidence * 100).toFixed(1) }}%
                  </span>
                </div>
                <div v-if="field.raw_text" class="field-item__raw">
                  原文：{{ field.raw_text }}
                </div>
              </div>
            </div>

            <div class="result-actions">
              <el-button @click="handleClearResult">
                <el-icon><RefreshLeft /></el-icon>重新识别
              </el-button>
              <el-button type="primary" @click="handleConvertToTask">
                <el-icon><Document /></el-icon>转为开票任务
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Promotion, InfoFilled, Loading, RefreshLeft, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { recognizeText } from '@/api/ai'
import { getEnterprises } from '@/api/enterprise'
import type { Enterprise, FieldExtraction, RecognitionResult } from '@/types'

const router = useRouter()

const recognizing = ref(false)
const enterpriseOptions = ref<Enterprise[]>([])
const result = ref<RecognitionResult | null>(null)
const editableFields = ref<FieldExtraction[]>([])

const form = reactive({
  enterprise_id: '',
  content: ''
})

const canRecognize = computed(() => form.enterprise_id && form.content.trim().length > 0)

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

function sourceTagType(source: string): 'primary' | 'success' | 'warning' | 'info' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info'> = {
    ocr: 'info',
    llm: 'primary',
    multimodal: 'success',
    rule: 'warning',
    knowledge_base: 'info'
  }
  return map[source] || 'info'
}

function confidenceColor(confidence: number) {
  if (confidence >= 0.8) return '#10B981'
  if (confidence >= 0.6) return '#F59E0B'
  return '#EF4444'
}

async function fetchEnterprises() {
  try {
    const res = await getEnterprises({ page: 1, page_size: 100 })
    enterpriseOptions.value = res.items
  } catch {
    // ignore
  }
}

async function handleRecognize() {
  if (!form.enterprise_id) {
    ElMessage.warning('请选择企业')
    return
  }
  if (!form.content.trim()) {
    ElMessage.warning('请输入开票指令')
    return
  }
  recognizing.value = true
  result.value = null
  try {
    const res = await recognizeText({
      content: form.content,
      enterprise_id: form.enterprise_id
    })
    result.value = res
    editableFields.value = res.fields.map((f) => ({ ...f, value: String(f.value ?? '') }))
    if (res.success) {
      ElMessage.success(`识别完成，共识别到 ${res.fields.length} 个字段`)
    } else {
      ElMessage.warning('识别完成，但存在部分问题')
    }
  } catch {
    // ignore
  } finally {
    recognizing.value = false
  }
}

function handleClear() {
  form.content = ''
  result.value = null
  editableFields.value = []
}

function handleClearResult() {
  result.value = null
  editableFields.value = []
}

function handleConvertToTask() {
  if (!editableFields.value.length) return
  // 将识别结果带到开票页面
  const fieldsData = editableFields.value.map((f) => ({ field_name: f.field_name, value: f.value }))
  sessionStorage.setItem('recognition_fields', JSON.stringify(fieldsData))
  sessionStorage.setItem('recognition_enterprise_id', form.enterprise_id)
  router.push({
    path: '/invoice/text',
    query: { from: 'recognition' }
  })
}

onMounted(() => {
  fetchEnterprises()
})
</script>

<style scoped lang="scss">
.recognition-text {
  .main-row {
    height: calc(100vh - 180px);
  }

  .input-card,
  .result-card {
    border-radius: 8px;
    height: 100%;

    :deep(.el-card__body) {
      height: calc(100% - 56px);
      overflow-y: auto;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .result-meta {
    display: flex;
    gap: 8px;
  }

  .input-tips {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    margin-top: 12px;
    color: #6b7280;
    font-size: 12px;
    line-height: 1.5;
  }

  .loading-state,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 300px;
    color: #6b7280;

    p {
      margin-top: 16px;
      font-size: 14px;
    }
  }

  .error-list {
    width: 100%;
    margin-top: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .warn-alert {
    margin-bottom: 16px;
  }

  .field-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .field-item {
    padding: 12px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #fff;
    transition: border-color 0.2s;

    &--low {
      border-color: #f59e0b;
      background: #fffbeb;
    }

    &__header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    &__name {
      font-size: 13px;
      font-weight: 500;
      color: #374151;
    }

    &__confidence {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 8px;

      .el-progress {
        flex: 1;
      }

      .confidence-text {
        font-size: 12px;
        font-weight: 600;
        min-width: 48px;
        text-align: right;
      }
    }

    &__raw {
      margin-top: 6px;
      font-size: 12px;
      color: #9ca3af;
      font-style: italic;
    }
  }

  .result-actions {
    display: flex;
    gap: 12px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
  }
}
</style>
