import request from './request'
import type { ProductRule, PaginatedResponse } from '@/types'

export interface ProductRuleQuery {
  page?: number
  page_size?: number
  enterprise_id?: string
  keyword?: string
}

export function getProductRules(params: ProductRuleQuery) {
  return request.get<unknown, PaginatedResponse<ProductRule>>('/product-rules', { params })
}

export function createProductRule(data: Partial<ProductRule>) {
  return request.post<unknown, ProductRule>('/product-rules', data)
}

export function updateProductRule(id: string, data: Partial<ProductRule>) {
  return request.put<unknown, ProductRule>(`/product-rules/${id}`, data)
}

export function deleteProductRule(id: string) {
  return request.delete<unknown, { success: boolean }>(`/product-rules/${id}`)
}

export function batchImportProductRules(enterpriseId: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<unknown, { total: number; success: number; failure: number; errors: any[] }>(
    '/product-rules/batch-import',
    formData,
    { params: { enterprise_id: enterpriseId } }
  )
}
