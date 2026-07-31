<template>
  <el-container class="main-layout">
    <!-- 顶部栏 -->
    <el-header class="main-layout__header">
      <div class="header-left">
        <div class="logo" @click="router.push('/dashboard')">
          <el-icon :size="24" color="#fff"><Document /></el-icon>
          <span class="logo-text">智能开票平台</span>
        </div>
        <el-icon class="collapse-btn" :size="20" color="#fff" @click="toggleCollapse">
          <Fold v-if="!isCollapse" />
          <Expand v-else />
        </el-icon>
      </div>
      <div class="header-center"></div>
      <div class="header-right">
        <!-- 租户切换（仅超管可见） -->
        <el-dropdown
          v-if="authStore.user?.is_super_admin"
          trigger="click"
          @command="handleSwitchTenant"
          class="tenant-switcher"
        >
          <div class="tenant-display">
            <el-icon><Switch /></el-icon>
            <span class="tenant-name">{{ currentTenantName || '选择租户' }}</span>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="t in tenants"
                :key="t.id"
                :command="t.id"
                :disabled="t.id === authStore.user?.tenant_id"
              >
                {{ t.name }}
                <el-tag v-if="t.id === authStore.user?.tenant_id" size="small" type="success" style="margin-left: 8px">
                  当前
                </el-tag>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-dropdown trigger="click" @command="handleCommand">
          <div class="user-info">
            <el-avatar :size="32" :src="authStore.user?.avatar">
              {{ authStore.user?.full_name?.charAt(0) || 'U' }}
            </el-avatar>
            <span class="user-name">{{ authStore.user?.full_name || '用户' }}</span>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-container class="main-layout__body">
      <!-- 左侧菜单 -->
      <el-aside :width="isCollapse ? '64px' : '220px'" class="main-layout__aside">
        <el-scrollbar>
          <el-menu
            :default-active="activeMenu"
            :collapse="isCollapse"
            :collapse-transition="false"
            router
            class="main-menu"
            background-color="#fff"
            text-color="#374151"
            active-text-color="#2563EB"
          >
            <template v-for="group in menuGroups" :key="group.title">
              <el-sub-menu v-if="group.children.length > 1" :index="group.title">
                <template #title>
                  <el-icon><component :is="group.icon" /></el-icon>
                  <span>{{ group.title }}</span>
                </template>
                <el-menu-item
                  v-for="item in group.children"
                  :key="item.path"
                  :index="item.path"
                >
                  <el-icon><component :is="item.icon" /></el-icon>
                  <template #title>{{ item.title }}</template>
                </el-menu-item>
              </el-sub-menu>
              <el-menu-item
                v-else
                :index="group.children[0].path"
              >
                <el-icon><component :is="group.children[0].icon" /></el-icon>
                <template #title>{{ group.children[0].title }}</template>
              </el-menu-item>
            </template>
          </el-menu>
        </el-scrollbar>
      </el-aside>

      <!-- 主内容区 -->
      <el-main class="main-layout__main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Document, Fold, Expand, Picture, Switch } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { listTenants, type TenantItem } from '@/api/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const isCollapse = ref(false)
const tenants = ref<TenantItem[]>([])
const currentTenantName = ref('')

const activeMenu = computed(() => route.path)

function toggleCollapse() {
    isCollapse.value = !isCollapse.value
}

async function loadTenants() {
    try {
        const res = await listTenants()
        tenants.value = res.tenants
        const current = res.tenants.find(t => t.id === res.current_tenant_id)
        currentTenantName.value = current?.name || ''
    } catch {
        // 非超管会 403，忽略
    }
}

async function handleSwitchTenant(tenantId: string) {
    try {
        await ElMessageBox.confirm(
            `切换到 "${tenants.value.find(t => t.id === tenantId)?.name}"？切换后所有数据将按新租户加载。`,
            '切换租户',
            { type: 'warning', confirmButtonText: '确认切换', cancelButtonText: '取消' }
        )
        await authStore.switchTenant(tenantId)
        ElMessage.success('已切换租户')
    } catch (e: any) {
        if (e !== 'cancel') ElMessage.error('切换失败')
    }
}

// 面向代账运营人员的精简主路径：导入批次 → 任务处理 → 异常处理。
// 通道、组织、审计、AI原始识别等低频配置功能仍保留路由，但不占用日常导航。
const menuGroups = [
  { title: '工作台', icon: 'Odometer', children: [{ title: '工作台', path: '/dashboard', icon: 'Odometer' }] },
  {
    title: '批量开票', icon: 'Files', children: [
      { title: '开票任务台', path: '/invoice-batches', icon: 'Files' },
      { title: '任务查询', path: '/invoice-tasks', icon: 'List' },
    ]
  },
  {
    title: '快速开票', icon: 'EditPen', children: [
      { title: '文字开票', path: '/invoice/text', icon: 'EditPen' },
      { title: '图片开票', path: '/invoice/image', icon: 'Picture' },
      { title: '文档开票', path: '/invoice/document', icon: 'Document' },
    ]
  },
  {
    title: '待处理', icon: 'Warning', children: [
      { title: '我的待办', path: '/work-items', icon: 'Bell' },
      { title: '异常处理', path: '/exceptions', icon: 'Warning' },
    ]
  },
  {
    title: '基础资料', icon: 'OfficeBuilding', children: [
      { title: '企业资料', path: '/enterprises', icon: 'OfficeBuilding' },
      { title: '客户抬头', path: '/customer-titles', icon: 'Avatar' },
      { title: '商品规则', path: '/product-rules', icon: 'Goods' },
    ]
  },
  { title: '数据分析', icon: 'DataAnalysis', children: [{ title: '开票统计', path: '/statistics', icon: 'DataAnalysis' }] },
  {
    title: '系统管理', icon: 'Setting', children: [
      { title: '客户提交链接', path: '/submission-links', icon: 'Link' },
      { title: '通道配置', path: '/channels', icon: 'Connection' },
      { title: '机构与人员', path: '/settings/organizations', icon: 'Share' },
      { title: '用户权限', path: '/settings/users', icon: 'User' },
      { title: '审计日志', path: '/audit-logs', icon: 'DocumentChecked' },
    ]
  },
]

async function handleCommand(command: string) {
  if (command !== 'logout') return
  await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
  authStore.logout()
  router.push('/login')
}

onMounted(async () => {
  if (authStore.isLoggedIn && !authStore.user) {
    try {
      await authStore.fetchUserInfo()
    } catch {
      // ignore
    }
  }
  await loadTenants()
})
</script>

<style scoped lang="scss">
.main-layout {
  height: 100vh;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background-color: #2563eb;
    padding: 0 20px;
    height: 56px;
    line-height: 56px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
    z-index: 10;
  }

  &__body {
    height: calc(100vh - 56px);
  }

  &__aside {
    background-color: #fff;
    border-right: 1px solid #e5e7eb;
    transition: width 0.3s;
    overflow: hidden;
  }

  &__main {
    background-color: #f6f8fb;
    padding: 0;
    overflow-y: auto;
  }
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;

  .logo {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;

    .logo-text {
      color: #fff;
      font-size: 16px;
      font-weight: 600;
      white-space: nowrap;
    }
  }

  .collapse-btn {
    cursor: pointer;
  }
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 0 40px;

  .global-search {
    max-width: 480px;
    width: 100%;
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;

  .tenant-switcher {
    cursor: pointer;
  }

  .tenant-display {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #fff;
    cursor: pointer;
    padding: 4px 12px;
    border-radius: 4px;
    transition: background 0.2s;

    &:hover {
      background: rgba(255, 255, 255, 0.1);
    }

    .tenant-name {
      font-size: 13px;
      max-width: 120px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .message-badge {
    display: flex;
    align-items: center;
  }

  .icon-btn {
    cursor: pointer;
  }

  .user-info {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;

    .user-name {
      color: #fff;
      font-size: 14px;
    }
  }
}

.main-menu {
  border-right: none;

  :deep(.el-menu-item),
  :deep(.el-sub-menu__title) {
    height: 44px;
    line-height: 44px;
  }

  :deep(.el-menu-item.is-active) {
    background-color: rgba(37, 99, 235, 0.08);
    border-right: 3px solid #2563eb;
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
