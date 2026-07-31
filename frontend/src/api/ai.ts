import request from './request'
import type { RecognitionResult, PaginatedResponse } from '@/types'

export function recognizeText(data: { content: string; enterprise_id: string }) {
  const formData = new FormData()
  formData.append('content', data.content)
  formData.append('enterprise_id', data.enterprise_id)
  return request.post<unknown, RecognitionResult>('/recognitions/text', formData)
}

export function recognizeImage(data: { file: File; enterprise_id: string }) {
  const formData = new FormData()
  formData.append('file', data.file)
  formData.append('enterprise_id', data.enterprise_id)
  return request.post<unknown, RecognitionResult>('/recognitions/image', formData)
}

export interface RecognitionHistoryQuery {
  page?: number
  page_size?: number
  source_type?: string
  start_date?: string
  end_date?: string
}

export interface RecognitionHistoryItem {
  id: string
  source_type: 'text' | 'image'
  enterprise_id: string
  enterprise_name: string
  status: string
  field_count: number
  avg_confidence: number
  created_at: string
}

export function getRecognitionHistory(params: RecognitionHistoryQuery) {
  return request.get<unknown, PaginatedResponse<RecognitionHistoryItem>>('/recognitions/history', { params })
}

export function getRecognitionDetail(id: string) {
  return request.get<unknown, RecognitionResult & { id: string; source_type: string; enterprise_name: string; created_at: string }>(`/recognitions/${id}`)
}

export interface RecognitionStatistics {
  total_count: number
  success_count: number
  today_count: number
  avg_confidence: number
  by_source: { source_type: string; count: number }[]
}

export function getRecognitionStatistics() {
  return request.get<unknown, RecognitionStatistics>('/recognitions/statistics')
}
