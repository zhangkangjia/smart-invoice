import request from './request'
import type { ExceptionCase, PaginatedResponse } from '@/types'

export interface ExceptionQuery {
  page?: number
  page_size?: number
  type?: string
  severity?: string
  status?: string
  enterprise_id?: string
}

export function getExceptions(params: ExceptionQuery) {
  return request.get<unknown, PaginatedResponse<ExceptionCase>>('/exceptions', { params })
}

export function getException(id: string) {
  return request.get<unknown, ExceptionCase>(`/exceptions/${id}`)
}

export function resolveException(id: string, data: { resolution: string; remark?: string }) {
  return request.post<unknown, ExceptionCase>(`/exceptions/${id}/resolve`, data)
}

export function batchFixExceptions(ids: string[], fixAction: string) {
  return request.post<unknown, { success_count: number; failed_count: number }>('/exceptions/batch-fix', { ids, fix_action: fixAction })
}
