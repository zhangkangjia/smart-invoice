import request from './request'
import type {
  BusinessRequest,
  InvoiceRequest,
  InvoiceTask,
  InvoiceResult,
  ImportBatch,
  AuditLog,
  PaginatedResponse
} from '@/types'

// ========== 业务请求 ==========

export interface TextRequestParams {
  content: string
  enterprise_id?: string
  remark?: string
}

export interface ImageRequestParams {
  enterprise_id?: string
  files: File[]
  remark?: string
}

export interface ExcelRequestParams {
  enterprise_id?: string
  file: File
  field_mapping?: Record<string, string>
  remark?: string
}

export function submitTextRequest(data: TextRequestParams) {
  const formData = new FormData()
  formData.append('content', data.content)
  if (data.enterprise_id) formData.append('enterprise_id', data.enterprise_id)
  if (data.remark) formData.append('remark', data.remark)
  return request.post<unknown, any>('/business-requests/text', formData)
}

export function submitImageRequest(data: ImageRequestParams) {
  const formData = new FormData()
  if (data.enterprise_id) formData.append('enterprise_id', data.enterprise_id)
  if (data.remark) formData.append('remark', data.remark)
  formData.append('file', data.files[0])
  return request.post<unknown, BusinessRequest>('/business-requests/image', formData)
}

export function submitExcelRequest(data: ExcelRequestParams) {
  const formData = new FormData()
  if (data.enterprise_id) formData.append('enterprise_id', data.enterprise_id)
  formData.append('file', data.file)
  if (data.field_mapping) formData.append('field_mapping', JSON.stringify(data.field_mapping))
  if (data.remark) formData.append('remark', data.remark)
  return request.post<unknown, any>('/business-requests/excel', formData)
}

export interface BusinessRequestQuery {
  page?: number
  page_size?: number
  enterprise_id?: string
  source_type?: string
  status?: string
}

export function getBusinessRequests(params: BusinessRequestQuery) {
  return request.get<unknown, PaginatedResponse<BusinessRequest>>('/business-requests', { params })
}

export function getBusinessRequest(id: string) {
  return request.get<unknown, BusinessRequest>(`/business-requests/${id}`)
}

// ========== 发票请求 ==========

export interface InvoiceRequestQuery {
  page?: number
  page_size?: number
  enterprise_id?: string
  status?: string
  start_date?: string
  end_date?: string
}

export function getInvoiceRequests(params: InvoiceRequestQuery) {
  return request.get<unknown, PaginatedResponse<InvoiceRequest>>('/invoice-requests', { params })
}

export function getInvoiceRequest(id: string) {
  return request.get<unknown, InvoiceRequest>(`/invoice-requests/${id}`)
}

// ========== 导入批次 ==========

export function getInvoiceBatches(params: BusinessRequestQuery) {
  return request.get<unknown, PaginatedResponse<ImportBatch>>('/invoice-batches', { params })
}

export function downloadInvoiceTemplate() {
  return request.get('/invoice-batches/template', { responseType: 'blob' })
}

export function getInvoiceBatch(id: string) {
  return request.get<unknown, ImportBatch>(`/invoice-batches/${id}`)
}

export function getInvoiceBatchTasks(id: string, params?: { page?: number; page_size?: number }) {
  return request.get<unknown, PaginatedResponse<InvoiceTask>>(`/invoice-batches/${id}/tasks`, { params })
}

// ========== 开票任务 ==========

export interface InvoiceTaskQuery {
  page?: number
  page_size?: number
  enterprise_id?: string
  status?: string
  batch_id?: string
  start_date?: string
  end_date?: string
}

export function getInvoiceTasks(params: InvoiceTaskQuery) {
  return request.get<unknown, PaginatedResponse<InvoiceTask>>('/invoice-tasks', { params })
}

export function getInvoiceTask(id: string) {
  return request.get<unknown, InvoiceTask>(`/invoice-tasks/${id}`)
}

export function retryInvoiceTask(id: string) {
  return request.post<unknown, InvoiceTask>(`/invoice-tasks/${id}/retry`)
}

export function cancelInvoiceTask(id: string) {
  return request.post<unknown, InvoiceTask>(`/invoice-tasks/${id}/cancel`)
}

export function getInvoiceTaskResult(id: string) {
  return request.get<unknown, InvoiceResult>(`/invoice-tasks/${id}/result`)
}

export function getInvoiceTaskAuditTrail(id: string) {
  return request.get<unknown, AuditLog[]>(`/invoice-tasks/${id}/audit-trail`)
}
