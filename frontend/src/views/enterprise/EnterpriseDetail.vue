<template>
  <div class="page-container">
    <PageHeader :title="enterprise?.name || '企业详情'" subtitle="企业管理详情页">
      <template #actions>
        <el-button @click="router.back()">返回</el-button>
        <el-dropdown trigger="click" @command="handleStatusChange">
          <el-button type="primary">
            状态管理<el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="opt in ENTERPRISE_STATUS_OPTIONS" :key="opt.value" :command="opt.value">
                {{ opt.label }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </PageHeader>

    <el-card v-loading="loading" shadow="never" class="detail-card">
      <el-tabs v-model="activeTab">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="info">
          <el-descriptions :column="2" border v-if="enterprise">
            <el-descriptions-item label="企业名称">{{ enterprise.name }}</el-descriptions-item>
            <el-descriptions-item label="税号">{{ enterprise.tax_number }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <StatusTag :status="enterprise.status" type="enterprise" />
            </el-descriptions-item>
            <el-descriptions-item label="服务等级">{{ getServiceLevelText(enterprise.service_level) }}</el-descriptions-item>
            <el-descriptions-item label="联系人">{{ enterprise.contact_person }}</el-descriptions-item>
            <el-descriptions-item label="联系电话">{{ enterprise.contact_phone }}</el-descriptions-item>
            <el-descriptions-item label="联系邮箱">{{ enterprise.contact_email }}</el-descriptions-item>
            <el-descriptions-item label="地址">{{ enterprise.address }}</el-descriptions-item>
            <el-descriptions-item label="法人">{{ enterprise.legal_person }}</el-descriptions-item>
            <el-descriptions-item label="行业">{{ enterprise.industry }}</el-descriptions-item>
            <el-descriptions-item label="负责人">{{ enterprise.account_manager_name }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(enterprise.created_at) }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- 开票配置 -->
        <el-tab-pane label="开票配置" name="config">
          <el-form v-if="config" :model="config" label-width="140px" style="max-width: 600px">
            <el-form-item label="默认税率">
              <el-input-number v-model="config.tax_rate" :min="0" :max="100" :precision="2" />
              <span style="margin-left: 8px">%</span>
            </el-form-item>
            <el-form-item label="发票类型">
              <el-select v-model="config.invoice_type" multiple style="width: 100%" placeholder="请选择发票类型">
                <el-option label="增值税普通发票" value="normal" />
                <el-option label="增值税专用发票" value="special" />
                <el-option label="电子普通发票" value="electronic_normal" />
                <el-option label="电子专用发票" value="electronic_special" />
              </el-select>
            </el-form-item>
            <el-form-item label="单张发票限额">
              <el-input-number v-model="config.invoice_limit" :min="0" />
              <span style="margin-left: 8px">元</span>
            </el-form-item>
            <el-form-item label="月度开票额度">
              <el-input-number v-model="config.monthly_quota" :min="0" />
              <span style="margin-left: 8px">元</span>
            </el-form-item>
            <el-form-item label="自动审核">
              <el-switch v-model="config.auto_approve" />
            </el-form-item>
            <el-form-item label="回调地址">
              <el-input v-model="config.callback_url" placeholder="请输入回调地址" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="config.remark" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="configSaving" @click="saveConfig">保存配置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 服务人员 -->
        <el-tab-pane label="服务人员" name="services">
          <el-table :data="services" stripe border>
            <el-table-column prop="service_type" label="服务类型" width="150" />
            <el-table-column prop="assignee_name" label="负责人" width="120" />
            <el-table-column label="开始日期" width="120">
              <template #default="{ row }">{{ formatDate(row.start_date) }}</template>
            </el-table-column>
            <el-table-column label="结束日期" width="120">
              <template #default="{ row }">{{ formatDate(row.end_date) }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100" />
          </el-table>
        </el-tab-pane>

        <!-- 客户抬头 -->
        <el-tab-pane label="客户抬头" name="customer-titles">
          <el-table :data="customerTitles" stripe border>
            <el-table-column prop="name" label="客户名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="tax_number" label="税号" width="180" />
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column label="默认" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.is_default" type="success" size="small">默认</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 商品规则 -->
        <el-tab-pane label="商品规则" name="product-rules">
          <el-table :data="productRules" stripe border>
            <el-table-column prop="product_name" label="商品名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="product_code" label="商品编码" width="150" />
            <el-table-column prop="tax_rate" label="税率" width="80">
              <template #default="{ row }">{{ row.tax_rate }}%</template>
            </el-table-column>
            <el-table-column prop="tax_category" label="税收分类" width="120" />
            <el-table-column prop="unit" label="单位" width="80" />
          </el-table>
        </el-tab-pane>

        <!-- 开票记录 -->
        <el-tab-pane label="开票记录" name="invoices">
          <el-table :data="invoices" stripe border>
            <el-table-column prop="invoice_no" label="发票号" width="150" />
            <el-table-column prop="customer_title" label="客户" min-width="150" show-overflow-tooltip />
            <el-table-column label="金额" width="120" align="right">
              <template #default="{ row }">¥{{ formatAmount(row.total_with_tax) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <StatusTag :status="row.status" type="task" />
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="120">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 健康度 -->
        <el-tab-pane label="健康度" name="health">
          <div v-if="health" class="health-dashboard">
            <el-row :gutter="16">
              <el-col :span="6">
                <el-card shadow="never" class="health-card">
                  <p class="health-label">健康评分</p>
                  <p class="health-value">{{ health.health_score }}</p>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="never" class="health-card">
                  <p class="health-label">成功率</p>
                  <p class="health-value">{{ health.success_rate }}%</p>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="never" class="health-card">
                  <p class="health-label">平均响应时间</p>
                  <p class="health-value">{{ health.avg_response_time }}ms</p>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="never" class="health-card">
                  <p class="health-label">异常数量</p>
                  <p class="health-value">{{ health.exception_count }}</p>
                </el-card>
              </el-col>
            </el-row>
          </div>
          <el-empty v-else description="暂无健康度数据" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  getEnterprise,
  getEnterpriseConfig,
  updateEnterpriseConfig,
  updateEnterpriseStatus,
  getServiceAssignments,
  getEnterpriseHealth
} from '@/api/enterprise'
import { getCustomerTitles } from '@/api/customer'
import { getProductRules } from '@/api/product'
import { getInvoiceRequests } from '@/api/invoice'
import { ENTERPRISE_STATUS_OPTIONS, SERVICE_LEVEL_OPTIONS } from '@/utils/constants'
import { formatAmount, formatDate, formatDateTime } from '@/utils/format'
import type { Enterprise, EnterpriseConfig, ServiceAssignment, EnterpriseHealth, CustomerTitle, ProductRule, InvoiceRequest } from '@/types'

const route = useRoute()
const router = useRouter()
const enterpriseId = route.params.id as string

const loading = ref(false)
const activeTab = ref('info')
const enterprise = ref<Enterprise | null>(null)
const config = ref<EnterpriseConfig | null>(null)
const services = ref<ServiceAssignment[]>([])
const customerTitles = ref<CustomerTitle[]>([])
const productRules = ref<ProductRule[]>([])
const invoices = ref<InvoiceRequest[]>([])
const health = ref<EnterpriseHealth | null>(null)
const configSaving = ref(false)

function getServiceLevelText(level: string) {
  return SERVICE_LEVEL_OPTIONS.find((o) => o.value === level)?.label || level
}

async function fetchEnterprise() {
  loading.value = true
  try {
    enterprise.value = await getEnterprise(enterpriseId)
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function fetchConfig() {
  try {
    config.value = await getEnterpriseConfig(enterpriseId)
  } catch {
    // ignore
  }
}

async function saveConfig() {
  if (!config.value) return
  configSaving.value = true
  try {
    await updateEnterpriseConfig(enterpriseId, config.value)
    ElMessage.success('配置保存成功')
  } catch {
    // ignore
  } finally {
    configSaving.value = false
  }
}

async function fetchServices() {
  try {
    services.value = await getServiceAssignments(enterpriseId)
  } catch {
    // ignore
  }
}

async function fetchCustomerTitles() {
  try {
    const res = await getCustomerTitles({ enterprise_id: enterpriseId, page: 1, page_size: 50 })
    customerTitles.value = res.items
  } catch {
    // ignore
  }
}

async function fetchProductRules() {
  try {
    const res = await getProductRules({ enterprise_id: enterpriseId, page: 1, page_size: 50 })
    productRules.value = res.items
  } catch {
    // ignore
  }
}

async function fetchInvoices() {
  try {
    const res = await getInvoiceRequests({ enterprise_id: enterpriseId, page: 1, page_size: 20 })
    invoices.value = res.items
  } catch {
    // ignore
  }
}

async function fetchHealth() {
  try {
    health.value = await getEnterpriseHealth(enterpriseId)
  } catch {
    // ignore
  }
}

async function handleStatusChange(status: string) {
  try {
    await ElMessageBox.confirm(`确定要变更企业状态吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await updateEnterpriseStatus(enterpriseId, status)
    ElMessage.success('状态变更成功')
    fetchEnterprise()
  } catch {
    // ignore
  }
}

onMounted(() => {
  fetchEnterprise()
  fetchConfig()
  fetchServices()
  fetchCustomerTitles()
  fetchProductRules()
  fetchInvoices()
  fetchHealth()
})
</script>

<style scoped lang="scss">
.detail-card {
  border-radius: 8px;
}

.health-dashboard {
  .health-card {
    text-align: center;
    border-radius: 8px;
  }

  .health-label {
    font-size: 13px;
    color: #6b7280;
    margin: 0 0 8px 0;
  }

  .health-value {
    font-size: 28px;
    font-weight: 600;
    color: #2563eb;
    margin: 0;
  }
}
</style>
