<template>
  <div class="wecom-callback">
    <div class="loading-box">
      <el-icon class="loading-icon" :size="48"><Loading /></el-icon>
      <p class="loading-text">{{ message }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Loading } from '@element-plus/icons-vue'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const message = ref('正在通过企业微信登录...')

onMounted(async () => {
  const code = route.query.code as string
  const redirect = (route.query.redirect as string) || '/dashboard'

  if (!code) {
    message.value = '未获取到企业微信授权code'
    setTimeout(() => router.push('/login'), 1500)
    return
  }

  try {
    const apiBase = import.meta.env.VITE_API_BASE_URL || ''
    const resp = await axios.get(`${apiBase}/api/v1/wechat/wecom/oauth-login`, {
      params: { code, redirect }
    })

    const { access_token, user } = resp.data
    authStore.setToken(access_token)
    authStore.setUser(user)
    message.value = '登录成功，正在进入工作台...'
    setTimeout(() => router.push(redirect), 300)
  } catch (err: any) {
    console.error('企业微信登录失败', err)
    message.value = err?.response?.data?.detail || '企业微信登录失败'
    setTimeout(() => router.push('/login'), 2000)
  }
})
</script>

<style scoped>
.wecom-callback {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #f5f7fa;
}
.loading-box {
  text-align: center;
  padding: 40px;
}
.loading-icon {
  color: #409eff;
  animation: rotating 2s linear infinite;
}
.loading-text {
  margin-top: 16px;
  color: #606266;
  font-size: 14px;
}
@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
