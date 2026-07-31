import request from './request'

export interface SubmissionInfo {
  enterprise_name: string
  requires_password: boolean
  is_active: boolean
  expires_at: string | null
  used_count: number
  max_uses: number | null
}

export function getSubmissionInfo(token: string) {
  return request.get<unknown, SubmissionInfo>(`/submissions/${token}/info`)
}

export function authSubmission(token: string, password: string) {
  const formData = new FormData()
  formData.append('password', password)
  return request.post<unknown, { authenticated: boolean }>(`/submissions/${token}/auth`, formData)
}

export interface SubmitViaLinkParams {
  content?: string
  files?: File[]
  external_order_no?: string
  customer_remark?: string
  contact_name?: string
  contact_phone?: string
  contact_email?: string
}

export function submitViaLink(token: string, data: SubmitViaLinkParams) {
  const formData = new FormData()
  if (data.content) formData.append('content', data.content)
  if (data.external_order_no) formData.append('external_order_no', data.external_order_no)
  if (data.customer_remark) formData.append('customer_remark', data.customer_remark)
  if (data.contact_name) formData.append('contact_name', data.contact_name)
  if (data.contact_phone) formData.append('contact_phone', data.contact_phone)
  if (data.contact_email) formData.append('contact_email', data.contact_email)
  if (data.files) {
    data.files.forEach((f) => formData.append('files', f))
  }
  return request.post<unknown, { request_id: string; request_no: string }>(`/submissions/${token}/submit`, formData)
}

export interface SubmissionStatusInfo {
  request_id: string
  request_no: string
  status: string
  enterprise_name: string
  created_at: string
  updated_at: string
  timeline: {
    step: string
    label: string
    status: 'done' | 'processing' | 'pending'
    timestamp: string | null
    description?: string
  }[]
  invoice_url?: string
  pdf_url?: string
  error_message?: string
}

export function getSubmissionStatus(token: string, requestId: string) {
  return request.get<unknown, SubmissionStatusInfo>(`/submissions/${token}/status`, { params: { request_id: requestId } })
}

export interface SubmissionHistoryItem {
  request_id: string
  request_no: string
  status: string
  created_at: string
  updated_at: string
}

export function getSubmissionHistory(token: string, params: { page: number; page_size: number }) {
  return request.get<unknown, { items: SubmissionHistoryItem[]; total: number }>(`/submissions/${token}/history`, { params })
}
