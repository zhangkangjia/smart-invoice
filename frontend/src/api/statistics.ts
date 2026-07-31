import request from './request'
import type { DashboardStats, EnterpriseStats } from '@/types'

export function getDashboardStats() {
  return request.get<unknown, DashboardStats>('/statistics/dashboard')
}

export function getEnterpriseStats(params: { start_date?: string; end_date?: string; enterprise_id?: string }) {
  return request.get<unknown, EnterpriseStats[]>('/statistics/enterprises', { params })
}
