<template>
  <div class="page-container recognition-image">
    <PageHeader title="图片识别" subtitle="上传开票相关图片，AI 自动识别字段并标注位置">
      <template #actions>
        <el-button @click="handleClear" :disabled="recognizing">清空</el-button>
        <el-button type="primary" :loading="recognizing" :disabled="!canRecognize" @click="handleRecognize">
          <el-icon><Promotion /></el-icon>开始识别
        </el-button>
      </template>
    </PageHeader>

    <el-card shadow="never" class="config-card">
      <el-form :inline="true">
        <el-form-item label="企业">
          <el-select v-model="form.enterprise_id" placeholder="请选择企业" filterable style="width: 240px">
            <el-option v-for="e in enterpriseOptions" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="main-row">
      <!-- 左侧：图片展示 -->
      <el-col :span="14">
        <el-card shadow="never" class="image-card">
          <template #header>
            <div class="card-header">
              <span>原图预览</span>
              <div v-if="fileList.length > 1" class="thumb-list">
                <div
                  v-for="(file, idx) in fileList"
                  :key="idx"
                  class="thumb-item"
                  :class="{ active: currentImageIndex === idx }"
                  @click="currentImageIndex = idx"
                >
                  <img :src="file.url" :alt="file.name" />
                </div>
              </div>
            </div>
          </template>

          <div v-if="fileList.length === 0" class="upload-zone">
            <el-upload
              drag
              multiple
              accept="image/*"
              :auto-upload="false"
              :show-file-list="false"
              :on-change="handleFileChange"
            >
              <el-icon class="el-icon--upload" :size="48"><UploadFilled /></el-icon>
              <div class="el-upload__text">将图片拖到此处，或<em>点击上传</em></div>
              <template #tip>
                <div class="el-upload__tip">支持 JPG、PNG、BMP 等格式，单张不超过 10MB，可多张上传</div>
              </template>
            </el-upload>
          </div>

          <div v-else class="image-viewer">
            <div class="image-wrapper" ref="imageWrapperRef">
              <img
                :src="fileList[currentImageIndex]?.url"
                :alt="fileList[currentImageIndex]?.name"
                class="source-image"
                @load="handleImageLoad"
                ref="imageRef"
              />
              <!-- 字段高亮框 -->
              <div
                v-for="(field, idx) in currentImageFields"
                :key="idx"
                class="field-box"
                :class="{ 'field-box--active': selectedFieldIndex === idx }"
                :style="getFieldBoxStyle(field)"
                @click="selectField(idx)"
              >
                <span class="field-box__label">{{ fieldDisplayName(field.field_name) }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：识别字段列表 -->
      <el-col :span="10">
        <el-card shadow="never" class="fields-card">
          <template #header>
            <div class="card-header">
              <span>识别字段</span>
              <el-tag v-if="result" size="small" type="info">{{ currentImageFields.length }} 个字段</el-tag>
            </div>
          </template>

          <div v-if="recognizing" class="loading-state">
            <el-icon class="is-loading" :size="32" color="#2563EB"><Loading /></el-icon>
            <p>正在识别中...</p>
          </div>

          <div v-else-if="!result" class="empty-state">
            <el-empty description="上传图片并点击识别后，结果将在此显示" />
          </div>

          <div v-else-if="allFields.length === 0" class="empty-state">
            <el-empty description="未识别到有效字段" />
          </div>

          <div v-else class="field-list">
            <div
              v-for="(field, idx) in currentImageFields"
              :key="idx"
              class="field-item"
              :class="{
                'field-item--active': selectedFieldIndex === idx,
                'field-item--low': field.confidence < 0.6
              }"
              @click="selectField(idx)"
            >
              <div class="field-item__header">
                <span class="field-item__name">{{ fieldDisplayName(field.field_name) }}</span>
                <el-tag size="small" :type="sourceTagType(field.source)">{{ sourceDisplayName(field.source) }}</el-tag>
              </div>
              <div class="field-item__value">{{ field.value }}</div>
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
            </div>
          </div>

          <div v-if="result && allFields.length > 0" class="result-actions">
            <el-button type="primary" @click="handleConvertToTask">
              <el-icon><Document /></el-icon>转为开票任务
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Promotion, UploadFilled, Loading, Document } from '@element-plus/icons-vue'
import { ElMessage, type UploadFile } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { recognizeImage } from '@/api/ai'
import { getEnterprises } from '@/api/enterprise'
import type { Enterprise, FieldExtraction, RecognitionResult } from '@/types'

const router = useRouter()

const recognizing = ref(false)
const enterpriseOptions = ref<Enterprise[]>([])
const fileList = ref<{ name: string; url: string; raw: File }[]>([])
const currentImageIndex = ref(0)
const selectedFieldIndex = ref(-1)
const result = ref<RecognitionResult | null>(null)
const imageRef = ref<HTMLImageElement>()
const imageWrapperRef = ref<HTMLDivElement>()
const naturalSize = reactive({ w: 0, h: 0 })

const form = reactive({
  enterprise_id: ''
})

const canRecognize = computed(() => form.enterprise_id && fileList.value.length > 0)

const allFields = computed<FieldExtraction[]>(() => result.value?.fields || [])

const currentImageFields = computed<FieldExtraction[]>(() => {
  return allFields.value.filter((f) => {
    if (!f.position) return currentImageIndex.value === 0
    return (f.position.page || 0) === currentImageIndex.value
  })
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
  invoice_no: '发票号码',
  invoice_code: '发票代码',
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

function getFieldBoxStyle(field: FieldExtraction) {
  if (!field.position || !naturalSize.w) return { display: 'none' }
  const { x = 0, y = 0, w = 0, h = 0 } = field.position
  return {
    left: `${(x / naturalSize.w) * 100}%`,
    top: `${(y / naturalSize.h) * 100}%`,
    width: `${(w / naturalSize.w) * 100}%`,
    height: `${(h / naturalSize.h) * 100}%`
  }
}

function selectField(idx: number) {
  selectedFieldIndex.value = selectedFieldIndex.value === idx ? -1 : idx
}

function handleImageLoad() {
  if (imageRef.value) {
    naturalSize.w = imageRef.value.naturalWidth
    naturalSize.h = imageRef.value.naturalHeight
  }
}

async function fetchEnterprises() {
  try {
    const res = await getEnterprises({ page: 1, page_size: 100 })
    enterpriseOptions.value = res.items
  } catch {
    // ignore
  }
}

function handleFileChange(file: UploadFile) {
  if (file.raw) {
    const url = URL.createObjectURL(file.raw)
    fileList.value.push({ name: file.name, url, raw: file.raw })
  }
}

async function handleRecognize() {
  if (!form.enterprise_id) {
    ElMessage.warning('请选择企业')
    return
  }
  if (fileList.value.length === 0) {
    ElMessage.warning('请上传至少一张图片')
    return
  }

  recognizing.value = true
  result.value = null
  selectedFieldIndex.value = -1

  try {
    // 逐张识别并合并结果
    const allFields: FieldExtraction[] = []
    let modelInfo = { model_name: '', model_version: '', processing_time_ms: 0 }
    const errors: string[] = []

    for (let i = 0; i < fileList.value.length; i++) {
      const file = fileList.value[i]
      const res = await recognizeImage({ file: file.raw, enterprise_id: form.enterprise_id })
      modelInfo = { model_name: res.model_name, model_version: res.model_version, processing_time_ms: modelInfo.processing_time_ms + res.processing_time_ms }
      if (res.fields.length > 0) {
        allFields.push(...res.fields.map((f) => ({
          ...f,
          position: f.position ? { ...f.position, page: i } : undefined
        })))
      }
      if (res.errors.length) errors.push(...res.errors)
    }

    result.value = {
      success: true,
      fields: allFields,
      errors,
      ...modelInfo
    }

    ElMessage.success(`识别完成，共识别到 ${allFields.length} 个字段`)
  } catch {
    // ignore
  } finally {
    recognizing.value = false
  }
}

function handleClear() {
  fileList.value = []
  result.value = null
  selectedFieldIndex.value = -1
  currentImageIndex.value = 0
}

function handleConvertToTask() {
  if (!allFields.value.length) return
  const fieldsData = allFields.value.map((f) => ({ field_name: f.field_name, value: String(f.value ?? '') }))
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
.recognition-image {
  .config-card {
    border-radius: 8px;
    margin-bottom: 16px;

    :deep(.el-card__body) {
      padding: 16px 20px;
    }
  }

  .main-row {
    height: calc(100vh - 260px);
  }

  .image-card,
  .fields-card {
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

  .thumb-list {
    display: flex;
    gap: 6px;

    .thumb-item {
      width: 40px;
      height: 40px;
      border: 2px solid transparent;
      border-radius: 4px;
      overflow: hidden;
      cursor: pointer;

      &.active {
        border-color: #2563eb;
      }

      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
    }
  }

  .upload-zone {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 400px;
  }

  .image-viewer {
    display: flex;
    justify-content: center;
    align-items: flex-start;
  }

  .image-wrapper {
    position: relative;
    display: inline-block;
    max-width: 100%;

    .source-image {
      max-width: 100%;
      max-height: 70vh;
      display: block;
    }

    .field-box {
      position: absolute;
      border: 2px solid #2563eb;
      background: rgba(37, 99, 235, 0.15);
      border-radius: 2px;
      cursor: pointer;
      transition: all 0.2s;

      &:hover,
      &--active {
        border-color: #f59e0b;
        background: rgba(245, 158, 11, 0.2);
        z-index: 10;
      }

      &__label {
        position: absolute;
        top: -20px;
        left: 0;
        background: #2563eb;
        color: #fff;
        font-size: 11px;
        padding: 1px 6px;
        border-radius: 2px;
        white-space: nowrap;
      }

      &--active &__label {
        background: #f59e0b;
      }
    }
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

  .field-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .field-item {
    padding: 10px 12px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      border-color: #2563eb;
    }

    &--active {
      border-color: #2563eb;
      background: rgba(37, 99, 235, 0.05);
    }

    &--low {
      border-color: #f59e0b;
      background: #fffbeb;
    }

    &__header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
    }

    &__name {
      font-size: 13px;
      font-weight: 500;
      color: #374151;
    }

    &__value {
      font-size: 14px;
      color: #1f2937;
      margin-bottom: 6px;
      word-break: break-all;
    }

    &__confidence {
      display: flex;
      align-items: center;
      gap: 8px;

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
  }

  .result-actions {
    display: flex;
    gap: 12px;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
  }
}
</style>
