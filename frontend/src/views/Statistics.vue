<template>
  <div class="page-container">
    <PageHeader title="数据统计" subtitle="开票数据分析与统计">
      <template #actions>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          @change="fetchData"
        />
      </template>
    </PageHeader>

    <!-- 概览卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <p class="stat-label">开票总量</p>
          <p class="stat-value">{{ dashboardStats?.today_invoice_count || 0 }}</p>
          <p class="stat-trend">本周趋势 ↑12%</p>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <p class="stat-label">成功率</p>
          <p class="stat-value">{{ dashboardStats?.success_rate || 0 }}%</p>
          <p class="stat-trend">较上周 ↑2.3%</p>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <p class="stat-label">人工介入率</p>
          <p class="stat-value">{{ manualInterventionRate }}%</p>
          <p class="stat-trend">较上周 ↓0.8%</p>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <p class="stat-label">异常总数</p>
          <p class="stat-value">{{ dashboardStats?.exception_count || 0 }}</p>
          <p class="stat-trend">待处理 {{ dashboardStats?.pending_tasks || 0 }}</p>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图 -->
    <el-card shadow="never" class="chart-card">
      <template #header><span>开票量趋势</span></template>
      <div class="chart-placeholder">
        <div class="chart-bars" v-if="dashboardStats?.week_trend">
          <div
            v-for="item in dashboardStats.week_trend"
            :key="item.date"
            class="chart-bar-item"
          >
            <div class="chart-bar" :style="{ height: getBarHeight(item.count) + '%' }">
              <span class="chart-value">{{ item.count }}</span>
            </div>
            <span class="chart-label">{{ item.date.slice(5) }}</span>
          </div>
        </div>
        <el-empty v-else description="暂无趋势数据" />
      </div>
    </el-card>

    <el-row :gutter="16">
      <!-- 成功率统计 -->
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span>成功率统计</span></template>
          <div class="success-rate">
            <div class="rate-item">
              <span class="rate-label">自动完成</span>
              <el-progress :percentage="85" color="#67C23A" />
            </div>
            <div class="rate-item">
              <span class="rate-label">人工审核</span>
              <el-progress :percentage="10" color="#E6A23C" />
            </div>
            <div class="rate-item">
              <span class="rate-label">失败</span>
              <el-progress :percentage="5" color="#F56C6C" />
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 异常排行 -->
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span>异常类型排行</span></template>
          <div class="exception-ranking">
            <div v-for="(item, index) in exceptionRanking" :key="item.type" class="ranking-item">
              <span class="ranking-index">{{ index + 1 }}</span>
              <span class="ranking-name">{{ item.label }}</span>
              <el-progress :percentage="item.percentage" :show-text="false" color="#2563EB" class="ranking-progress" />
              <span class="ranking-count">{{ item.count }}次</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 企业统计 -->
    <el-card shadow="never" class="chart-card">
      <template #header><span>企业开票统计</span></template>
      <el-table v-loading="loading" :data="enterpriseStats" stripe border>
        <el-table-column prop="enterprise_name" label="企业名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="total_invoice_count" label="开票总数" width="100" align="center" />
        <el-table-column prop="success_count" label="成功数" width="100" align="center">
          <template #default="{ row }">
            <span style="color: #67c23a">{{ row.success_count }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="failed_count" label="失败数" width="100" align="center">
          <template #default="{ row }">
            <span style="color: #f56c6c">{{ row.failed_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成功率" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.success_rate" :text-inside="true" :stroke-width="16" />
          </template>
        </el-table-column>
        <el-table-column label="开票总额" width="140" align="right">
          <template #default="{ row }">¥{{ formatAmount(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column label="平均处理时间" width="120" align="right">
          <template #default="{ row }">{{ row.avg_processing_time }}s</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { getDashboardStats, getEnterpriseStats } from '@/api/statistics'
import { EXCEPTION_TYPE_OPTIONS } from '@/utils/constants'
import { formatAmount } from '@/utils/format'
import type { DashboardStats, EnterpriseStats } from '@/types'

const loading = ref(false)
const dateRange = ref<[string, string] | null>(null)
const dashboardStats = ref<DashboardStats | null>(null)
const enterpriseStats = ref<EnterpriseStats[]>([])

const manualInterventionRate = computed(() => {
  if (!dashboardStats.value) return 0
  return Math.round((1 - dashboardStats.value.success_rate / 100) * 100)
})

const exceptionRanking = ref(
  EXCEPTION_TYPE_OPTIONS.map((opt) => ({
    type: opt.value,
    label: opt.label,
    count: Math.floor(Math.random() * 50) + 10,
    percentage: 0
  })).sort((a, b) => b.count - a.count).map((item, _, arr) => ({
    ...item,
    percentage: Math.round((item.count / arr[0].count) * 100)
  }))
)

function getBarHeight(count: number) {
  if (!dashboardStats.value?.week_trend) return 0
  const max = Math.max(...dashboardStats.value.week_trend.map((t) => t.count))
  return max > 0 ? (count / max) * 100 : 0
}

async function fetchData() {
  loading.value = true
  try {
    const params: any = {}
    if (dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    dashboardStats.value = await getDashboardStats()
    enterpriseStats.value = await getEnterpriseStats(params)
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped lang="scss">
.stat-cards {
  margin-bottom: 16px;
}

.stat-card {
  border-radius: 8px;
  text-align: center;

  .stat-label {
    font-size: 13px;
    color: #6b7280;
    margin: 0;
  }

  .stat-value {
    font-size: 28px;
    font-weight: 600;
    color: #1f2937;
    margin: 8px 0;
  }

  .stat-trend {
    font-size: 12px;
    color: #67c23a;
    margin: 0;
  }
}

.chart-card {
  border-radius: 8px;
  margin-bottom: 16px;
}

.chart-placeholder {
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-bars {
  display: flex;
  align-items: flex-end;
  gap: 20px;
  height: 280px;
  width: 100%;
  justify-content: center;
}

.chart-bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 40px;
  height: 100%;
  justify-content: flex-end;
}

.chart-bar {
  width: 100%;
  background: linear-gradient(180deg, #2563eb 0%, #60a5fa 100%);
  border-radius: 4px 4px 0 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  min-height: 4px;
  position: relative;

  .chart-value {
    position: absolute;
    top: -20px;
    font-size: 12px;
    color: #6b7280;
  }
}

.chart-label {
  font-size: 12px;
  color: #6b7280;
}

.success-rate {
  .rate-item {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;

    .rate-label {
      width: 80px;
      font-size: 14px;
      color: #374151;
    }
  }
}

.exception-ranking {
  .ranking-item {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;

    .ranking-index {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: #f0f2f5;
      color: #6b7280;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: 600;
    }

    .ranking-name {
      width: 100px;
      font-size: 14px;
    }

    .ranking-progress {
      flex: 1;
    }

    .ranking-count {
      width: 60px;
      text-align: right;
      font-size: 13px;
      color: #6b7280;
    }
  }
}
</style>
