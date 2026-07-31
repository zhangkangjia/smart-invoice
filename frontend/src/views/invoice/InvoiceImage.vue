<template>
  <div class="page-container">
    <PageHeader title="图片开票" subtitle="上传开票资料，系统自动识别销方企业、购方抬头及发票明细" />

    <el-alert
      title="无需预先选择企业或客户抬头"
      description="系统会从图片中的销方税号、企业名称或专属提交上下文自动路由；购方资料由OCR识别并匹配历史抬头。仅在多家销方企业且资料没有销方信息时，系统会阻止开票以避免错开。"
      type="info"
      :closable="false"
      show-icon
      class="guide-alert"
    />

    <el-card shadow="never" class="main-card">
      <el-form label-width="72px">
        <el-form-item label="备注">
          <el-input v-model="remark" placeholder="可选：内部备注，不影响识别" />
        </el-form-item>
      </el-form>

      <el-upload
        ref="uploadRef"
        drag
        accept="image/*"
        :auto-upload="false"
        :limit="1"
        :file-list="fileList"
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
        list-type="picture"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将开票申请单、聊天截图或营业执照拖到此处，或<em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 JPG、PNG、BMP、WEBP，单张不超过 10MB。上传后自动完成识别和开票。</div>
        </template>
      </el-upload>

      <div class="actions">
        <el-button type="primary" :loading="submitting" :disabled="fileList.length === 0" @click="handleSubmit">
          <el-icon><Promotion /></el-icon>智能识别并开票
        </el-button>
        <el-button @click="handleClear">清空</el-button>
      </div>
    </el-card>

    <el-card v-if="result" shadow="never" class="result-card">
      <template #header>处理结果</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="自动匹配销方">{{ result.enterprise_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理状态">{{ result.status }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="result.invoice_tasks || []" class="task-table" border empty-text="暂无开票任务">
        <el-table-column prop="buyer_name" label="购方名称" min-width="180" />
        <el-table-column prop="total_with_tax" label="价税合计" width="140">
          <template #default="{ row }">¥{{ formatAmount(row.total_with_tax) }}</template>
        </el-table-column>
        <el-table-column prop="task_status" label="开票状态" width="130" />
        <el-table-column prop="invoice_number" label="发票号码" min-width="160" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/invoice-tasks/${row.task_id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { UploadFilled, Promotion } from '@element-plus/icons-vue'
import { ElMessage, type UploadFile } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { submitImageRequest } from '@/api/invoice'
import { formatAmount } from '@/utils/format'

const router = useRouter()
const submitting = ref(false)
const fileList = ref<UploadFile[]>([])
const remark = ref('')
const result = ref<any>(null)

function handleFileChange(file: UploadFile) {
  fileList.value = [file]
}

function handleFileRemove() {
  fileList.value = []
}

async function handleSubmit() {
  const rawFile = fileList.value[0]?.raw
  if (!rawFile) {
    ElMessage.warning('请上传一张图片')
    return
  }

  submitting.value = true
  result.value = null
  try {
    const res = await submitImageRequest({ files: [rawFile], remark: remark.value })
    result.value = res
    ElMessage.success('图片已识别并完成开票处理')
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    const message = typeof detail === 'object' ? detail.message : detail
    ElMessage.error(message || error?.message || '图片开票失败')
  } finally {
    submitting.value = false
  }
}

function handleClear() {
  fileList.value = []
  remark.value = ''
  result.value = null
}
</script>

<style scoped lang="scss">
.guide-alert { margin-bottom: 16px; }
.main-card, .result-card { border-radius: 8px; }
.result-card { margin-top: 16px; }
.actions { display: flex; gap: 12px; margin-top: 20px; }
.task-table { margin-top: 16px; }
</style>
