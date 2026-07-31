import request from './request'
import type { AuditLog, PaginatedResponse } from '@/types'

export interface AuditLogQuery {
  page?: number
  page_size?: number
  user_id?: string
  module?: string
  action?: string
  status?: string
  start_date?: string
  end_date?: string
}

export function getAuditLogs(params: AuditLogQuery) {
  return request.get<unknown, PaginatedResponse<AuditLog>>('/audit-logs', { params })
}
