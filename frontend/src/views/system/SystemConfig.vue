<template>
  <div class="page-container">
    <PageHeader title="系统配置" subtitle="统一管理企业微信、微信、百望云、AI 等集成配置">
      <template #actions>
        <el-button type="primary" :loading="saving" @click="handleSave">
          <el-icon><Check /></el-icon>保存配置
        </el-button>
      </template>
    </PageHeader>

    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
      <template #title>
        敏感信息（Secret/Key）保存后显示为 ******，留空表示不修改。
        部分配置修改后需重启服务才生效。
      </template>
    </el-alert>

    <el-row :gutter="16">
      <el-col :span="6">
        <el-card shadow="never" class="menu-card">
          <el-menu :default-active="activeCategory" @select="handleSelect">
            <el-menu-item v-for="g in groups" :key="g.category" :index="g.category">
              <el-icon><component :is="g.icon" /></el-icon>
              <span>{{ g.title }}</span>
              <el-tag v-if="g.items.some(i => i.has_value)" size="small" type="success" style="margin-left: 8px">已配置</el-tag>
            </el-menu-item>
          </el-menu>
        </el-card>
      </el-col>

      <el-col :span="18">
        <el-card v-loading="loading" shadow="never">
          <template v-for="g in groups" :key="g.category">
            <div v-show="g.category === activeCategory">
              <div class="group-header">
                <el-icon :size="20"><component :is="g.icon" /></el-icon>
                <h3>{{ g.title }}</h3>
                <el-button link type="primary" :loading="testing === g.category" @click="handleTest(g.category)">
                  测试连通性
                </el-button>
              </div>
              <p class="group-desc">{{ g.description }}</p>

              <el-form label-width="160px" class="config-form">
                <el-form-item v-for="item in g.items" :key="item.key" :label="item.label">
                  <el-input
                    v-model="formData[item.key]"
                    :type="item.is_secret && item.has_value && !showSecret[item.key] ? 'password' : 'text'"
                    :placeholder="item.has_value ? '已配置（留空不修改）' : '请输入'"
                    clearable
                  >
                    <template v-if="item.is_secret && item.has_value" #append>
                      <el-button @click="showSecret[item.key] = !showSecret[item.key]">
                        {{ showSecret[item.key] ? '隐藏' : '显示' }}
                      </el-button>
                    </template>
                  </el-input>
                  <div class="item-desc">{{ item.description }}</div>
                </el-form-item>
              </el-form>
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- 测试结果 -->
    <el-dialog v-model="testResultVisible" title="测试结果" width="480px">
      <el-result
        :icon="testResult?.ok ? 'success' : 'error'"
        :title="testResult?.ok ? '连接成功' : '连接失败'"
        :sub-title="testResult?.message || testResult?.error"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import request from '@/api/request'

const loading = ref(false)
const saving = ref(false)
const testing = ref('')
const activeCategory = ref('wecom')
const groups = ref<any[]>([])
const formData = reactive<Record<string, string>>({})
const showSecret = reactive<Record<string, boolean>>({})
const testResultVisible = ref(false)
const testResult = ref<any>(null)

async function fetchConfig() {
  loading.value = true
  try {
    const res = await request.get('/system-config') as any
    groups.value = res.groups
    // 初始化表单数据
    for (const g of res.groups) {
      for (const item of g.items) {
        // 敏感字段已配置时留空（表示不修改）
        if (item.is_secret && item.has_value) {
          formData[item.key] = ''
        } else {
          formData[item.key] = item.value || ''
        }
        showSecret[item.key] = false
      }
    }
  } catch {
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

function handleSelect(index: string) {
  activeCategory.value = index
}

async function handleSave() {
  saving.value = true
  try {
    // 只提交有值的字段
    const data: Record<string, string> = {}
    for (const key in formData) {
      if (formData[key]) {
        data[key] = formData[key]
      }
    }
    const res = await request.put('/system-config', data) as any
    ElMessage.success(res.message || '保存成功')
    await fetchConfig()  // 重新加载
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTest(category: string) {
  testing.value = category
  try {
    const res = await request.post(`/system-config/test/${category}`) as any
    testResult.value = res
    testResultVisible.value = true
  } catch (e: any) {
    testResult.value = {
      ok: false,
      error: e?.response?.data?.detail || '测试失败',
    }
    testResultVisible.value = true
  } finally {
    testing.value = ''
  }
}

onMounted(() => {
  fetchConfig()
})
</script>

<style scoped lang="scss">
.menu-card {
  :deep(.el-card__body) {
    padding: 8px;
  }
}
.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;

  h3 {
    margin: 0;
    flex: 1;
    font-size: 16px;
  }
}
.group-desc {
  color: #909399;
  font-size: 13px;
  margin: 0 0 24px 28px;
}
.config-form {
  max-width: 700px;
}
.item-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
