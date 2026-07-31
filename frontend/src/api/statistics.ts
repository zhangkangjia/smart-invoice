import request from './request'
import type { DashboardStats, EnterpriseStats } from '@/types'

export function getDashboardStats() {
  return request.get<unknown, DashboardStats>('/statistics/dashboard')
}

export function getEnterpriseStats(params: { start_date?: string; end_date?: string; enterprise_id?: string }) {
  const enterpriseId = params.enterprise_id
  if (enterpriseId) {
    return request.get<unknown, EnterpriseStats>(`/statistics/enterprise/${enterpriseId}`, { params: { start_date: params.start_date, end_date: params.end_date } })
  }
  return Promise.resolve({} as EnterpriseStats)
}
