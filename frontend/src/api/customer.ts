import request from './request'
import type { CustomerTitle, CustomerContact, PaginatedResponse } from '@/types'

export interface CustomerTitleQuery {
  page?: number
  page_size?: number
  enterprise_id?: string
  name?: string
  tax_no?: string
}

export function getCustomerTitles(params: CustomerTitleQuery) {
  return request.get<unknown, PaginatedResponse<CustomerTitle>>('/customer-titles', { params })
}

export function lookupCustomerByTaxNo(taxNo: string, enterpriseId?: string) {
  return request.get<unknown, {
    tax_no: string
    found_locally: boolean
    found_remote: boolean
    customer_title: CustomerTitle | null
    suggestion: Partial<CustomerTitle> | null
    message: string
  }>('/customer-titles/lookup/by-tax-no', { params: { tax_no: taxNo, enterprise_id: enterpriseId } })
}

export function createCustomerTitle(data: Partial<CustomerTitle>) {
  return request.post<unknown, CustomerTitle>('/customer-titles', data)
}

export function updateCustomerTitle(id: string, data: Partial<CustomerTitle>) {
  return request.put<unknown, CustomerTitle>(`/customer-titles/${id}`, data)
}

export function deleteCustomerTitle(id: string) {
  return request.delete<unknown, void>(`/customer-titles/${id}`)
}

export function batchImportCustomerTitles(enterpriseId: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<unknown, { total: number; success: number; failure: number; errors: any[] }>(
    '/customer-titles/batch-import',
    formData,
    { params: { enterprise_id: enterpriseId } }
  )
}

export function downloadCustomerTitleTemplate() {
  return request.get<unknown, Blob>('/customer-titles/template/download', { responseType: 'blob' })
}

export function getCustomerContacts(customerTitleId: string) {
  return request.get<unknown, CustomerContact[]>(`/customer-titles/${customerTitleId}/contacts`)
}

export function createCustomerContact(customerTitleId: string, data: Partial<CustomerContact>) {
  return request.post<unknown, CustomerContact>(`/customer-titles/${customerTitleId}/contacts`, data)
}
