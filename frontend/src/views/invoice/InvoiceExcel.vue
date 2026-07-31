<template>
  <div class="page-container">
    <PageHeader title="Excel批量开票" subtitle="上传标准Excel，系统按“企业名称”列自动路由并逐行识别购方抬头" />

    <el-alert
      title="无需预先选择企业或客户抬头"
      description="标准模板中包含“企业名称”时自动匹配销方；没有该列时，系统仅在当前只有一家启用企业时自动处理。每一行的“购方名称、购方税号、商品名称、数量、单价、税率”直接用于开票。"
      type="info"
      :closable="false"
      show-icon
      class="guide-alert"
    />

    <el-card shadow="never" class="main-card">
      <el-steps :active="currentStep" finish-status="success" align-center class="steps">
        <el-step title="上传文件" />
        <el-step title="自动解析" />
        <el-step title="创建开票任务" />
      </el-steps>

      <div v-show="currentStep === 0" class="step-content">
        <el-upload
          drag
          accept=".xlsx"
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">将 Excel 文件拖到此处，或<em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">
              支持 .xlsx 标准模板。必填列：购方名称、商品名称、数量、单价；建议列：企业名称、购方税号、税率、接收邮箱。
            </div>
          </template>
        </el-upload>
        <div class="step-actions">
          <el-button type="primary" :disabled="!uploadFile" @click="currentStep = 1">下一步</el-button>
        </div>
      </div>

      <div v-show="currentStep === 1" class="step-content">
        <el-result icon="info" title="系统将自动解析标准列" sub-title="上传后将校验每一行数据，正常行自动开票，错误行会保留在处理结果中。" />
        <div class="template-fields">
          <el-tag v-for="field in fields" :key="field" class="field-tag">{{ field }}</el-tag>
        </div>
        <div class="step-actions">
          <el-button @click="currentStep = 0">上一步</el-button>
          <el-button type="primary" @click="currentStep = 2">确认并创建任务</el-button>
        </div>
      </div>

      <div v-show="currentStep === 2" class="step-content">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="文件名">{{ uploadFile?.name }}</el-descriptions-item>
          <el-descriptions-item label="处理规则">自动识别销方企业、逐行生成开票任务、异常行不阻塞其他行</el-descriptions-item>
        </el-descriptions>
        <div class="step-actions">
          <el-button @click="currentStep = 1">上一步</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">开始智能开票</el-button>
        </div>
      </div>
    </el-card>

    <el-card v-if="result" shadow="never" class="result-card">
      <template #header>批量处理结果</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="自动匹配销方">{{ result.enterprise_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理状态">{{ result.status }}</el-descriptions-item>
        <el-descriptions-item label="处理阶段">{{ result.current_stage || '-' }}</el-descriptions-item>
        <el-descriptions-item label="开票任务数">{{ result.invoice_tasks?.length || 0 }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="result.invoice_tasks || []" border class="task-table" empty-text="没有成功创建开票任务">
        <el-table-column prop="buyer_name" label="购方名称" min-width="180" />
        <el-table-column prop="total_with_tax" label="价税合计" width="140">
          <template #default="{ row }">¥{{ formatAmount(row.total_with_tax) }}</template>
        </el-table-column>
        <el-table-column prop="task_status" label="状态" width="130" />
        <el-table-column prop="invoice_number" label="发票号码" min-width="160" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }"><el-button link type="primary" @click="router.push(`/invoice-tasks/${row.task_id}`)">详情</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { submitExcelRequest } from '@/api/invoice'
import { formatAmount } from '@/utils/format'

const router = useRouter()
const currentStep = ref(0)
const uploadFile = ref<File | null>(null)
const submitting = ref(false)
const result = ref<any>(null)
const fields = ['企业名称（建议）', '购方名称', '购方税号', '商品名称', '规格', '单位', '数量', '单价', '税率', '接收邮箱', '备注']

function handleFileChange(file: any) {
  uploadFile.value = file.raw
}

function handleFileRemove() {
  uploadFile.value = null
}

async function handleSubmit() {
  if (!uploadFile.value) {
    ElMessage.warning('请上传Excel文件')
    return
  }
  submitting.value = true
  result.value = null
  try {
    const res = await submitExcelRequest({ file: uploadFile.value, field_mapping: {} })
    result.value = res
    ElMessage.success(`批量处理完成，已创建 ${res.invoice_tasks?.length || 0} 个开票任务`)
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    const message = typeof detail === 'object' ? detail.message : detail
    ElMessage.error(message || error?.message || 'Excel处理失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.guide-alert { margin-bottom: 16px; }
.main-card, .result-card { border-radius: 8px; }
.steps { margin-bottom: 30px; }
.step-content { min-height: 280px; }
.step-actions { display: flex; justify-content: center; gap: 12px; margin-top: 30px; }
.template-fields { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
.field-tag { margin: 0; }
.result-card { margin-top: 16px; }
.task-table { margin-top: 16px; }
</style>
