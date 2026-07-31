import request from './request'
import type { SubmissionLink, PaginatedResponse } from '@/types'

export interface SubmissionLinkQuery {
  enterprise_id?: string
  page?: number
  page_size?: number
}

export function getSubmissionLinks(params: SubmissionLinkQuery) {
  return request.get<unknown, PaginatedResponse<SubmissionLink>>('/submission-links', { params })
}

export interface CreateSubmissionLinkParams {
  enterprise_id: string
  link_type: 'one_time' | 'permanent' | 'expiring'
  password?: string
  max_uses?: number
  expires_at?: string
}

export function createSubmissionLink(data: CreateSubmissionLinkParams) {
  return request.post<unknown, SubmissionLink>('/submission-links', data)
}

export function deactivateLink(id: string) {
  return request.delete<unknown, void>(`/submission-links/${id}`)
}

export function regenerateToken(id: string) {
  return request.post<unknown, SubmissionLink>(`/submission-links/${id}/regenerate`)
}
