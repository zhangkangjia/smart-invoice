import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/wecom-callback',
    name: 'WeComCallback',
    component: () => import('@/views/WeComCallback.vue'),
    meta: { title: '企业微信登录', requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '工作台', icon: 'Odometer' }
      },
      {
        path: 'enterprises',
        name: 'EnterpriseList',
        component: () => import('@/views/enterprise/EnterpriseList.vue'),
        meta: { title: '企业列表', icon: 'OfficeBuilding' }
      },
      {
        path: 'enterprises/:id',
        name: 'EnterpriseDetail',
        component: () => import('@/views/enterprise/EnterpriseDetail.vue'),
        meta: { title: '企业详情', hidden: true }
      },
      {
        path: 'customer-titles',
        name: 'CustomerTitleList',
        component: () => import('@/views/customer/CustomerTitleList.vue'),
        meta: { title: '客户抬头', icon: 'Avatar' }
      },
      {
        path: 'product-rules',
        name: 'ProductRuleList',
        component: () => import('@/views/product/ProductRuleList.vue'),
        meta: { title: '商品规则', icon: 'Goods' }
      },
      {
        path: 'invoice/text',
        name: 'InvoiceText',
        component: () => import('@/views/invoice/InvoiceText.vue'),
        meta: { title: '文字开票', icon: 'EditPen' }
      },
      {
        path: 'invoice/image',
        name: 'InvoiceImage',
        component: () => import('@/views/invoice/InvoiceImage.vue'),
        meta: { title: '图片开票', icon: 'Picture' }
      },
      {
        path: 'invoice/excel',
        redirect: '/invoice-batches',
        meta: { title: '批量开票', hidden: true }
      },
      {
        path: 'invoice-batches',
        name: 'InvoiceBatchList',
        component: () => import('@/views/invoice/InvoiceBatchList.vue'),
        meta: { title: '批次列表', icon: 'Files' }
      },
      {
        path: 'invoice-tasks',
        name: 'InvoiceTaskList',
        component: () => import('@/views/invoice/InvoiceTaskList.vue'),
        meta: { title: '任务列表', icon: 'List' }
      },
      {
        path: 'invoice-tasks/:id',
        name: 'InvoiceTaskDetail',
        component: () => import('@/views/invoice/InvoiceTaskDetail.vue'),
        meta: { title: '任务详情', hidden: true }
      },
      {
        path: 'work-items',
        name: 'WorkItemList',
        component: () => import('@/views/work/WorkItemList.vue'),
        meta: { title: '我的待办', icon: 'Bell' }
      },
      {
        path: 'exceptions',
        name: 'ExceptionList',
        component: () => import('@/views/exception/ExceptionList.vue'),
        meta: { title: '异常中心', icon: 'Warning' }
      },
      {
        path: 'statistics',
        name: 'Statistics',
        component: () => import('@/views/Statistics.vue'),
        meta: { title: '数据统计', icon: 'DataAnalysis' }
      },
      {
        path: 'audit-logs',
        name: 'AuditLogList',
        component: () => import('@/views/audit/AuditLogList.vue'),
        meta: { title: '审计日志', icon: 'DocumentChecked' }
      },
      {
        path: 'channels',
        name: 'ChannelList',
        component: () => import('@/views/channel/ChannelList.vue'),
        meta: { title: '通道管理', icon: 'Connection' }
      },
      {
        path: 'settings/organizations',
        name: 'OrganizationList',
        component: () => import('@/views/organization/OrganizationList.vue'),
        meta: { title: '机构管理', icon: 'Share' }
      },
      {
        path: 'settings/users',
        name: 'UserList',
        component: () => import('@/views/user/UserList.vue'),
        meta: { title: '用户管理', icon: 'User' }
      },
      {
        path: 'ai/text',
        name: 'AIText',
        component: () => import('@/views/ai/RecognitionText.vue'),
        meta: { title: '文字识别', icon: 'Document' }
      },
      {
        path: 'ai/image',
        name: 'AIImage',
        component: () => import('@/views/ai/RecognitionImage.vue'),
        meta: { title: '图片识别', icon: 'Picture' }
      },
      {
        path: 'ai/history',
        name: 'AIHistory',
        component: () => import('@/views/ai/RecognitionHistory.vue'),
        meta: { title: '识别记录', icon: 'List' }
      },
      {
        path: 'submission-links',
        name: 'SubmissionLinks',
        component: () => import('@/views/submission/SubmissionLinkList.vue'),
        meta: { title: '提交链接', icon: 'Link' }
      }
    ]
  },
  {
    path: '/submit/:token',
    name: 'CustomerSubmit',
    component: () => import('@/views/submission/CustomerSubmit.vue'),
    meta: { title: '开票资料提交', requiresAuth: false }
  },
  {
    path: '/submit/:token/status',
    name: 'SubmissionStatus',
    component: () => import('@/views/submission/SubmissionStatus.vue'),
    meta: { title: '查询进度', requiresAuth: false }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  const isLoggedIn = authStore.isLoggedIn

  if (to.meta.requiresAuth !== false && !isLoggedIn) {
    next({ name: 'Login' })
  } else if (to.name === 'Login' && isLoggedIn) {
    next({ path: '/dashboard' })
  } else {
    // 设置页面标题
    if (to.meta.title) {
      document.title = `${to.meta.title} - 智能开票平台`
    }
    next()
  }
})

export default router
