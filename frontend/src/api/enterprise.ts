import request from './request'
import type { Enterprise, EnterpriseConfig, ServiceAssignment, EnterpriseHealth, PaginatedResponse } from '@/types'

export interface EnterpriseQuery {
  page?: number
  page_size?: number
  name?: string
  status?: string
}

export function getEnterprises(params: EnterpriseQuery) {
  return request.get<unknown, PaginatedResponse<Enterprise>>('/enterprises', { params })
}

export function getEnterprise(id: string) {
  return request.get<unknown, Enterprise>(`/enterprises/${id}`)
}

export function createEnterprise(data: Partial<Enterprise> & { status?: string }) {
  return request.post<unknown, Enterprise>('/enterprises', data)
}

export function updateEnterprise(id: string, data: Partial<Enterprise>) {
  return request.put<unknown, Enterprise>(`/enterprises/${id}`, data)
}

export function updateEnterpriseStatus(id: string, status: string) {
  return request.patch<unknown, Enterprise>(`/enterprises/${id}/status`, null, { params: { status } })
}

export function getEnterpriseConfig(id: string) {
  return request.get<unknown, EnterpriseConfig>(`/enterprises/${id}/config`)
}

export function updateEnterpriseConfig(id: string, data: Partial<EnterpriseConfig>) {
  return request.put<unknown, EnterpriseConfig>(`/enterprises/${id}/config`, data)
}

export function getServiceAssignments(id: string) {
  return request.get<unknown, ServiceAssignment[]>(`/enterprises/${id}/assignments`)
}

export function assignService(id: string, data: Partial<ServiceAssignment>) {
  return request.post<unknown, ServiceAssignment>(`/enterprises/${id}/assignments`, data)
}

export function getEnterpriseHealth(id: string) {
  return request.get<unknown, EnterpriseHealth>(`/enterprises/${id}/health`)
}

export function lookupByTaxNo(taxNo: string) {
  return request.get<unknown, {
    tax_no: string
    found_locally: boolean
    found_remote: boolean
    enterprise: Enterprise | null
    suggestion: Partial<Enterprise> | null
    message: string
  }>('/enterprises/lookup/by-tax-no', { params: { tax_no: taxNo } })
}
