<template>
  <div class="page-container">
    <PageHeader title="文档开票" subtitle="上传 Word/PDF 文档，AI 自动识别内容并开票">
      <template #actions>
        <el-button @click="showHelp = !showHelp" link>使用说明</el-button>
      </template>
    </PageHeader>

    <el-alert v-if="showHelp" type="info" :closable="false" show-icon style="margin-bottom: 16px">
      <template #title>
        支持上传 .docx / .pdf / .txt 文件，系统会自动提取文档内容（段落+表格），
        通过 AI 识别开票要素（购方信息、商品、金额、税号等），自动匹配销方企业后开票。
      </template>
    </el-alert>

    <el-card shadow="never">
      <el-upload
        v-if="!result"
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".docx,.pdf,.txt"
        :on-change="handleFileChange"
        drag
        class="upload-area"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将文档拖到此处，或<em>点击选择</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .docx / .pdf / .txt 格式，单文件大小不超过 10MB
          </div>
        </template>
      </el-upload>

      <div v-else class="result-area">
        <el-result
          :icon="result.status === 'success' ? 'success' : 'warning'"
          :title="resultTitle"
          :sub-title="resultSubTitle"
        />

        <div v-if="result.invoice_tasks?.length" class="invoice-list">
          <el-divider content-position="left">开票结果</el-divider>
          <el-table :data="result.invoice_tasks" border size="small">
            <el-table-column prop="invoice_number" label="发票号" width="180" />
            <el-table-column prop="buyer_name" label="购方" min-width="160" show-overflow-tooltip />
            <el-table-column prop="total_with_tax" label="价税合计" width="120" align="right">
              <template #default="{ row }">¥{{ row.total_with_tax }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
                  {{ row.status === 'success' ? '成功' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="actions">
          <el-button @click="resetForm">继续上传</el-button>
        </div>
      </div>

      <div v-if="!result && selectedFile" class="submit-bar">
        <el-text type="info">已选: {{ selectedFile.name }} ({{ formatSize(selectedFile.size) }})</el-text>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          开始识别并开票
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, type UploadFile } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import request from '@/api/request'

const showHelp = ref(false)
const selectedFile = ref<File | null>(null)
const submitting = ref(false)
const result = ref<any>(null)

function handleFileChange(file: UploadFile) {
  selectedFile.value = file.raw || null
  result.value = null
}

function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(1) + 'MB'
}

const resultTitle = ref('')
const resultSubTitle = ref('')

async function handleSubmit() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  submitting.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const resp = await request.post('/business-requests/document', formData, {
      timeout: 120000,
    })
    result.value = resp as any
    const tasks = (resp as any).invoice_tasks || []
    const success = tasks.filter((t: any) => t.status === 'success').length
    resultTitle.value = success ? '开票成功' : '处理完成'
    resultSubTitle.value = `共 ${tasks.length} 张，成功 ${success} 张`
    ElMessage.success('处理完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  selectedFile.value = null
  result.value = null
}
</script>

<style scoped lang="scss">
.upload-area {
  margin: 20px 0;
}
.result-area {
  padding: 20px 0;
}
.invoice-list {
  margin-top: 16px;
}
.actions {
  margin-top: 24px;
  text-align: center;
}
.submit-bar {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
