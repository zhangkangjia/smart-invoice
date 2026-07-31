import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '@/api/auth'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const refreshToken = ref<string>(localStorage.getItem('refreshToken') || '')
  const user = ref<User | null>(null)

  const isLoggedIn = computed(() => !!token.value)

  function setToken(newToken: string, newRefreshToken: string) {
    token.value = newToken
    refreshToken.value = newRefreshToken
    localStorage.setItem('token', newToken)
    localStorage.setItem('refreshToken', newRefreshToken)
  }

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    setToken(res.access_token, res.refresh_token)
    await fetchUserInfo()
    return res
  }

  async function fetchUserInfo() {
    const res = await authApi.getMe()
    user.value = res
    return res
  }

  function logout() {
    token.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
  }

  async function refresh() {
    try {
      const res = await authApi.refresh(refreshToken.value)
      setToken(res.access_token, res.refresh_token)
      return res
    } catch (error) {
      logout()
      throw error
    }
  }

  return {
    token,
    refreshToken,
    user,
    isLoggedIn,
    setToken,
    login,
    logout,
    refresh,
    fetchUserInfo
  }
})
