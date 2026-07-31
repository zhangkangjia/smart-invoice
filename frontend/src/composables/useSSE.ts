import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

export interface SSEEvent {
  id?: string
  type: string
  title?: string
  message?: string
  data?: any
  timestamp?: string
  level?: 'info' | 'success' | 'warning' | 'error'
  event?: string
}

export function useSSE() {
  const events = ref<SSEEvent[]>([])
  const connected = ref(false)
  let eventSource: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let currentToken = ''

  function connect() {
    const authStore = useAuthStore()
    currentToken = authStore.token
    if (!currentToken) return

    if (eventSource) eventSource.close()
    eventSource = new EventSource(`/api/v1/sse/events?token=${encodeURIComponent(currentToken)}`)

    eventSource.onopen = () => {
      connected.value = true
    }

    eventSource.onerror = () => {
      connected.value = false
      if (eventSource) {
        eventSource.close()
        eventSource = null
      }
      // 自动重连（最多 10 秒一次）
      if (reconnectTimer) clearTimeout(reconnectTimer)
      reconnectTimer = setTimeout(() => {
        if (currentToken) connect()
      }, 10000)
    }

    eventSource.onmessage = (e) => {
      try {
        const data: SSEEvent = JSON.parse(e.data)
        events.value.unshift(data)
        if (events.value.length > 50) events.value.pop()
      } catch {
        // ignore parse errors (heartbeat etc.)
      }
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    connected.value = false
  }

  function clearEvents() {
    events.value = []
  }

  onUnmounted(disconnect)

  return { events, connected, connect, disconnect, clearEvents }
}
