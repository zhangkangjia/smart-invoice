<template>
  <el-dialog
    v-model="visible"
    title="批量操作影响预览"
    width="640px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div v-loading="loading" class="preview-content">
      <div v-if="result" class="preview-body">
        <!-- 概览统计 -->
        <el-row :gutter="12" class="stat-row">
          <el-col :span="6">
            <div class="stat-box stat-box--total">
              <p class="stat-box__value">{{ result.total_count }}</p>
              <p class="stat-box__label">影响总数</p>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-box stat-box--success">
              <p class="stat-box__value">{{ result.executable_count }}</p>
              <p class="stat-box__label">可执行</p>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-box stat-box--danger">
              <p class="stat-box__value">{{ result.non_executable_count }}</p>
              <p class="stat-box__label">无法执行</p>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-box stat-box--warning">
              <p class="stat-box__value">{{ result.high_risk_count }}</p>
              <p class="stat-box__label">高风险</p>
            </div>
          </el-col>
        </el-row>

        <!-- 结果未知 -->
        <el-alert
          v-if="result.unknown_result_count > 0"
          type="info"
          :closable="false"
          show-icon
          class="info-alert"
        >
          <template #title>有 {{ result.unknown_result_count }} 个任务结果未知，执行后可能需要人工确认</template>
        </el-alert>

        <!-- 审批提示 -->
        <el-alert
          v-if="result.requires_approval"
          type="warning"
          :closable="false"
          show-icon
          class="info-alert"
        >
          <template #title>本次批量操作涉及高风险任务，需要审批后才能执行</template>
        </el-alert>

        <!-- 无法执行原因分布 -->
        <div v-if="Object.keys(result.non_executable_reasons).length > 0" class="reason-section">
          <p class="section-title">无法执行原因分布</p>
          <div class="reason-list">
            <div v-for="(count, reason) in result.non_executable_reasons" :key="reason" class="reason-item">
              <span class="reason-item__name">{{ reason }}</span>
              <el-tag type="danger" size="small">{{ count }}</el-tag>
            </div>
          </div>
        </div>

        <!-- 详情列表 -->
        <div v-if="result.details.length > 0" class="detail-section">
          <p class="section-title">影响详情</p>
          <el-table :data="result.details.slice(0, 10)" stripe size="small" max-height="240">
            <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
            <el-table-column label="可执行" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.executable ? 'success' : 'danger'" size="small">
                  {{ row.executable ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="风险等级" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="riskTagType(row.risk_level)" size="small">{{ row.risk_level || '低' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="原因" min-width="120" show-overflow-tooltip />
          </el-table>
          <p v-if="result.details.length > 10" class="more-tip">
            还有 {{ result.details.length - 10 }} 条记录未显示...
          </p>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button
        type="primary"
        :loading="executing"
        :disabled="!result || result.executable_count === 0"
        @click="handleConfirm"
      >
        确认执行（{{ result?.executable_count || 0 }}项）
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { previewBatchOperation, executeBatchOperation } from '@/api/batch'
import type { BatchPreviewResult } from '@/types'

const props = defineProps<{
  modelValue: boolean
  operationType: 'invoice' | 'retry' | 'rule_change' | 'enterprise_pause' | 'channel_switch'
  targetIds: string[]
  params?: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirmed', result: any): void
}>()

const visible = ref(props.modelValue)
const loading = ref(false)
const executing = ref(false)
const result = ref<(BatchPreviewResult & { preview_token: string }) | null>(null)

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val && !result.value) {
    fetchPreview()
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

async function fetchPreview() {
  loading.value = true
  result.value = null
  try {
    const res = await previewBatchOperation({
      operation_type: props.operationType,
      target_ids: props.targetIds,
      params: props.params
    })
    result.value = res
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

function riskTagType(level: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    低: 'success',
    中: 'warning',
    高: 'danger',
    low: 'success',
    medium: 'warning',
    high: 'danger'
  }
  return map[level] || 'info'
}

async function handleConfirm() {
  if (!result.value) return
  executing.value = true
  try {
    const res = await executeBatchOperation({
      operation_type: props.operationType,
      target_ids: props.targetIds,
      params: props.params,
      preview_token: result.value.preview_token
    })
    ElMessage.success(`执行完成：成功 ${res.success_count} 项，失败 ${res.failed_count} 项`)
    emit('confirmed', res)
    handleClose()
  } catch {
    // ignore
  } finally {
    executing.value = false
  }
}

function handleClose() {
  visible.value = false
  result.value = null
}

// 当 props 变化时重新预览
watch(() => [props.operationType, props.targetIds], () => {
  if (visible.value) {
    fetchPreview()
  }
})
</script>

<style scoped lang="scss">
.preview-content {
  min-height: 200px;
}

.preview-body {
  .stat-row {
    margin-bottom: 16px;
  }

  .stat-box {
    text-align: center;
    padding: 16px 8px;
    border-radius: 8px;

    &__value {
      font-size: 28px;
      font-weight: 600;
      margin: 0 0 4px 0;
    }

    &__label {
      font-size: 12px;
      color: #6b7280;
      margin: 0;
    }

    &--total {
      background: #f0f5ff;
      .stat-box__value { color: #2563eb; }
    }

    &--success {
      background: #f0fdf4;
      .stat-box__value { color: #10b981; }
    }

    &--danger {
      background: #fef2f2;
      .stat-box__value { color: #ef4444; }
    }

    &--warning {
      background: #fffbeb;
      .stat-box__value { color: #f59e0b; }
    }
  }

  .info-alert {
    margin-bottom: 12px;
  }

  .reason-section,
  .detail-section {
    margin-top: 16px;

    .section-title {
      font-size: 14px;
      font-weight: 500;
      color: #1f2937;
      margin-bottom: 10px;
    }
  }

  .reason-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .reason-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: #fef2f2;
    border-radius: 6px;

    &__name {
      font-size: 13px;
      color: #374151;
    }
  }

  .more-tip {
    text-align: center;
    font-size: 12px;
    color: #9ca3af;
    margin-top: 8px;
  }
}
</style>
