import request from './request'
import type { ChannelInfo } from '@/types'

export function getChannels() {
  return request.get<unknown, ChannelInfo[]>('/channels')
}

export interface ChannelCapabilityDetail {
  provider_code: string
  capability: string
  supported: boolean
  description: string
}

export function getChannelCapabilities(providerCode: string) {
  return request.get<unknown, ChannelCapabilityDetail[]>(`/channels/${providerCode}/capabilities`)
}

export interface ChannelHealthInfo {
  provider_code: string
  healthy: boolean
  latency_ms: number
  last_check_at: string
  error_message?: string
}

export function checkChannelHealth(providerCode: string) {
  return request.get<unknown, ChannelHealthInfo>(`/channels/${providerCode}/health`)
}

export interface ChannelBinding {
  enterprise_id: string
  enterprise_name: string
  provider_code: string
  provider_name: string
  credentials: Record<string, any>
  bound_at: string
}

export function getChannelBinding(enterpriseId: string) {
  return request.get<unknown, ChannelBinding>(`/channels/enterprises/${enterpriseId}/binding`)
}

export function bindChannel(enterpriseId: string, data: { provider_code: string; credentials: Record<string, any> }) {
  return request.post<unknown, ChannelBinding>(`/channels/enterprises/${enterpriseId}/binding`, data)
}

export function unbindChannel(enterpriseId: string) {
  return request.delete<unknown, void>(`/channels/enterprises/${enterpriseId}/binding`)
}

export interface EnterpriseQuota {
  enterprise_id: string
  provider_code: string
  monthly_limit: number
  monthly_used: number
  remaining: number
  reset_at: string
}

export function getEnterpriseQuota(enterpriseId: string) {
  return request.get<unknown, EnterpriseQuota>(`/channels/enterprises/${enterpriseId}/quota`)
}
