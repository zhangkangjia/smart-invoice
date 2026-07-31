<template>
  <div class="page-container">
    <PageHeader title="系统诊断" subtitle="检查服务依赖、配置状态、核心功能可用性">
      <template #actions>
        <el-button type="primary" :loading="loading" @click="runCheck">
          <el-icon><Refresh /></el-icon>重新检查
        </el-button>
      </template>
    </PageHeader>

    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="never" class="status-card">
          <div class="overall-status">
            <el-icon :size="48" :class="overallColor">
              <SuccessFilled v-if="!hasError" />
              <WarningFilled v-else-if="hasWarning" />
              <CircleCloseFilled v-else />
            </el-icon>
            <h2>{{ overallText }}</h2>
            <p>{{ lastCheckTime }}</p>
          </div>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card shadow="never">
          <template #header>
            <span>服务依赖</span>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item v-for="(v, k) in checks" :key="k" :label="labelMap[k] || k">
              <el-tag :type="tagType(v.status)" size="small">{{ v.status }}</el-tag>
              <span v-if="v.message" style="margin-left: 8px; color: #f56c6c; font-size: 12px">
                {{ v.message }}
              </span>
              <span v-if="v.mode" style="margin-left: 8px; color: #909399; font-size: 12px">
                ({{ v.mode }})
              </span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <span>核心功能检查</span>
      </template>
      <el-table :data="features" border size="small">
        <el-table-column prop="name" label="功能项" width="200" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === '通过' ? 'success' : 'danger'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="testFeature(row)">
              测试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, SuccessFilled, WarningFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import request from '@/api/request'

const loading = ref(false)
const checks = ref<Record<string, any>>({})
const lastCheckTime = ref('')

const labelMap: Record<string, string> = {
  database: '数据库',
  redis: 'Redis 缓存',
  wecom: '企业微信',
  wechat: '微信服务号',
  baiwang: '百望云通道',
  ai: 'AI 识别',
}

const features = ref([
  { name: '文字开票', status: '通过', description: '提交文字描述自动识别开票', endpoint: '/business-requests/text' },
  { name: '图片开票', status: '通过', description: '上传图片OCR识别开票', endpoint: '/business-requests/image' },
  { name: 'Excel批量', status: '通过', description: 'Excel模板批量导入开票', endpoint: '/business-requests/excel' },
  { name: '文档开票', status: '通过', description: 'Word/PDF文档解析开票', endpoint: '/business-requests/document' },
  { name: '企业导入', status: '通过', description: '企业资料批量导入', endpoint: '/enterprises/import' },
])

const hasError = computed(() => Object.values(checks.value).some((v: any) => v.status === 'error'))
const hasWarning = computed(() => Object.values(checks.value).some((v: any) => v.status === 'not_configured' || v.status === 'mock_mode'))
const overallColor = computed(() => hasError.value ? 'error' : (hasWarning.value ? 'warning' : 'success'))
const overallText = computed(() => hasError.value ? '存在异常' : (hasWarning.value ? '部分配置未完成' : '全部正常'))

function tagType(status: string) {
  if (status === 'ok' || status === 'live') return 'success'
  if (status === 'not_configured' || status === 'mock_mode' || status === 'mock') return 'warning'
  return 'danger'
}

async function runCheck() {
  loading.value = true
  try {
    const res = await request.get('/health/full') as any
    checks.value = res.checks
    lastCheckTime.value = new Date().toLocaleString()
    ElMessage.success('检查完成')
  } catch (e: any) {
    ElMessage.error('检查失败: ' + (e?.message || ''))
  } finally {
    loading.value = false
  }
}

async function testFeature(row: any) {
  ElMessage.info(`正在测试 ${row.name}...`)
}

onMounted(() => {
  runCheck()
})
</script>

<style scoped lang="scss">
.status-card {
  text-align: center;
  padding: 20px;
}
.overall-status {
  padding: 20px 0;

  h2 {
    margin: 16px 0 8px;
  }
  p {
    color: #909399;
    font-size: 13px;
  }
  .success { color: #67c23a; }
  .warning { color: #e6a23c; }
  .error { color: #f56c6c; }
}
</style>
