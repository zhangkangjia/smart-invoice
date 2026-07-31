import request from './request'
import type { WorkItem, PaginatedResponse } from '@/types'

export interface WorkItemQuery {
  page?: number
  page_size?: number
  type?: string
  status?: string
  priority?: string
  assignee_id?: string
  enterprise_id?: string
}

export function getWorkItems(params: WorkItemQuery) {
  return request.get<unknown, PaginatedResponse<WorkItem>>('/work-items', { params })
}

export function getWorkItem(id: string) {
  return request.get<unknown, WorkItem>(`/work-items/${id}`)
}

export function assignWorkItem(id: string, assigneeId: string) {
  return request.post<unknown, WorkItem>(`/work-items/${id}/assign`, { assignee_id: assigneeId })
}

export function transferWorkItem(id: string, assigneeId: string, reason: string) {
  return request.post<unknown, WorkItem>(`/work-items/${id}/transfer`, { assignee_id: assigneeId, reason })
}

export function resolveWorkItem(id: string, data: { resolution: string; remark?: string }) {
  return request.post<unknown, WorkItem>(`/work-items/${id}/resolve`, data)
}
