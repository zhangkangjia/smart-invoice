import request from './request'
import type { Agency, Branch, Department, Team } from '@/types'

export function getAgencies() {
  return request.get<unknown, Agency[]>('/organizations/agencies')
}

export function createAgency(data: Partial<Agency>) {
  return request.post<unknown, Agency>('/organizations/agencies', data)
}

export function getBranches(agencyId?: string) {
  return request.get<unknown, Branch[]>('/organizations/branches', { params: { agency_id: agencyId } })
}

export function createBranch(data: Partial<Branch>) {
  return request.post<unknown, Branch>('/organizations/branches', data)
}

export function getDepartments(branchId?: string) {
  return request.get<unknown, Department[]>('/organizations/departments', { params: { branch_id: branchId } })
}

export function getTeams(departmentId?: string) {
  return request.get<unknown, Team[]>('/organizations/teams', { params: { department_id: departmentId } })
}
