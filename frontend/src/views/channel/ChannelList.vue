<template>
  <div class="page-container">
    <PageHeader title="通道管理" subtitle="管理开票服务通道与健康状态">
      <template #actions>
        <el-button @click="fetchAllHealth" :loading="healthLoading">
          <el-icon><Refresh /></el-icon>刷新健康状态
        </el-button>
      </template>
    </PageHeader>

    <!-- 通道列表 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <span>通道列表</span>
      </template>
      <el-table v-loading="loading" :data="channels" stripe border>
        <el-table-column prop="provider_name" label="通道名称" min-width="140" />
        <el-table-column prop="provider_code" label="编码" width="120" />
        <el-table-column label="健康状态" width="120" align="center">
          <template #default="{ row }">
            <div class="health-cell">
              <span class="health-dot" :class="getHealthClass(row)"></span>
              <span>{{ getHealthText(row) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="能力矩阵" min-width="320">
          <template #default="{ row }">
            <div class="capability-tags">
              <el-tag
                v-for="cap in capabilityList"
                :key="cap.key"
                :type="getCapability(row, cap.key) ? 'success' : 'info'"
                size="small"
                effect="plain"
              >
                {{ cap.label }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleHealthCheck(row)">健康检查</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 能力对比表 -->
    <el-card shadow="never" class="compare-card">
      <template #header>
        <span>通道能力对比</span>
      </template>
      <el-table :data="capabilityTableData" stripe border size="small">
        <el-table-column prop="capability" label="能力项" width="160" fixed />
        <el-table-column
          v-for="ch in channels"
          :key="ch.provider_code"
          :label="ch.provider_name"
          align="center"
          min-width="120"
        >
          <template #default="{ row }">
            <el-icon v-if="row[ch.provider_code]" color="#10B981" :size="16"><CircleCheck /></el-icon>
            <el-icon v-else color="#d1d5db" :size="16"><CircleClose /></el-icon>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 健康检查结果 -->
    <el-dialog v-model="healthDialogVisible" title="健康检查结果" width="440px">
      <div v-loading="healthChecking">
        <div v-if="healthResult" class="health-result">
          <div class="health-result__header">
            <span class="health-dot" :class="healthResult.healthy ? 'dot--success' : 'dot--danger'"></span>
            <span class="health-result__title">{{ healthResult.provider_code }}</span>
            <el-tag :type="healthResult.healthy ? 'success' : 'danger'" size="small">
              {{ healthResult.healthy ? '健康' : '异常' }}
            </el-tag>
          </div>
          <el-descriptions :column="1" border size="small" class="health-desc">
            <el-descriptions-item label="延迟">{{ healthResult.latency_ms }}ms</el-descriptions-item>
            <el-descriptions-item label="检查时间">{{ formatDateTime(healthResult.last_check_at) }}</el-descriptions-item>
            <el-descriptions-item v-if="healthResult.error_message" label="错误信息">
              {{ healthResult.error_message }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { getChannels, checkChannelHealth, type ChannelHealthInfo } from '@/api/channel'
import { formatDateTime } from '@/utils/format'
import type { ChannelInfo } from '@/types'

const loading = ref(false)
const healthLoading = ref(false)
const channels = ref<ChannelInfo[]>([])
const healthMap = ref<Record<string, boolean>>({})
const healthDialogVisible = ref(false)
const healthChecking = ref(false)
const healthResult = ref<ChannelHealthInfo | null>(null)

const capabilityList = [
  { key: 'electronic_invoice', label: '电子发票' },
  { key: 'special_invoice', label: '专票' },
  { key: 'red_invoice', label: '红冲' },
  { key: 'batch_invoice', label: '批量' },
  { key: 'refund', label: '退款' },
  { key: 'preview', label: '预览' }
]

const capabilityTableData = computed(() => {
  return capabilityList.map((cap) => {
    const row: Record<string, any> = { capability: cap.label }
    channels.value.forEach((ch) => {
      row[ch.provider_code] = getCapability(ch, cap.key)
    })
    return row
  })
})

function getCapability(channel: ChannelInfo, key: string): boolean {
  return !!(channel.capabilities as any)?.[key]
}

function getHealthClass(channel: ChannelInfo) {
  const healthy = healthMap.value[channel.provider_code]
  if (healthy === undefined) return 'dot--unknown'
  return healthy ? 'dot--success' : 'dot--danger'
}

function getHealthText(channel: ChannelInfo) {
  const healthy = healthMap.value[channel.provider_code]
  if (healthy === undefined) return '未检查'
  return healthy ? '健康' : '异常'
}

async function fetchChannels() {
  loading.value = true
  try {
    const res = await getChannels()
    channels.value = res
    // 初始化健康状态
    res.forEach((ch) => {
      healthMap.value[ch.provider_code] = ch.healthy
    })
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function fetchAllHealth() {
  healthLoading.value = true
  try {
    await Promise.all(
      channels.value.map(async (ch) => {
        try {
          const res = await checkChannelHealth(ch.provider_code)
          healthMap.value[ch.provider_code] = res.healthy
        } catch {
          healthMap.value[ch.provider_code] = false
        }
      })
    )
    ElMessage.success('健康状态已刷新')
  } catch {
    // ignore
  } finally {
    healthLoading.value = false
  }
}

async function handleHealthCheck(channel: ChannelInfo) {
  healthDialogVisible.value = true
  healthChecking.value = true
  healthResult.value = null
  try {
    const res = await checkChannelHealth(channel.provider_code)
    healthResult.value = res
    healthMap.value[channel.provider_code] = res.healthy
  } catch {
    // ignore
  } finally {
    healthChecking.value = false
  }
}

onMounted(() => {
  fetchChannels()
})
</script>

<style scoped lang="scss">
.table-card,
.compare-card {
  border-radius: 8px;
  margin-bottom: 16px;
}

.health-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: center;
  font-size: 13px;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;

  &.dot--success {
    background: #10b981;
    box-shadow: 0 0 4px rgba(16, 185, 129, 0.4);
  }

  &.dot--danger {
    background: #ef4444;
    box-shadow: 0 0 4px rgba(239, 68, 68, 0.4);
  }

  &.dot--unknown {
    background: #d1d5db;
  }
}

.capability-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.health-result {
  &__header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;

    .health-dot {
      width: 10px;
      height: 10px;
    }

    .health-result__title {
      flex: 1;
      font-size: 16px;
      font-weight: 500;
    }
  }

  .health-desc {
    margin-top: 8px;
  }
}
</style>
