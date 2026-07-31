import request from './request'
import type { ImportBatch, InvoiceTask, PaginatedResponse } from '@/types'

export interface BatchQuery {
  page?: number
  page_size?: number
  source_type?: string
}

export function getBatches(params: BatchQuery) {
  return request.get<unknown, PaginatedResponse<ImportBatch>>('/invoice-batches', { params })
}

export function downloadBatchTemplate() {
  return request.get('/invoice-batches/template', { responseType: 'blob' })
}

export function getBatchDetail(id: string) {
  return request.get<unknown, ImportBatch>(`/invoice-batches/${id}`)
}

export function getBatchTasks(id: string, params?: { page?: number; page_size?: number; status?: string }) {
  return request.get<unknown, PaginatedResponse<InvoiceTask & { enterprise_name?: string; buyer_name?: string; buyer_tax_no?: string; total_with_tax?: number; invoice_number?: string }>>(`/invoice-batches/${id}/tasks`, { params })
}

export function exportFailedRows(batchId: string) {
  return request.get(`/invoice-batches/${batchId}/failed-rows/export`, { responseType: 'blob' })
}

export function retryBatchTask(taskId: string) {
  return request.post(`/invoice-tasks/${taskId}/retry`)
}

export function cancelBatchTask(taskId: string) {
  return request.post(`/invoice-tasks/${taskId}/cancel`)
}
