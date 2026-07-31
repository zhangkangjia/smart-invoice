import request from './request'
import type { User } from '@/types'

export interface LoginParams {
  username: string
  password: string
}

export interface LoginResult {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export function login(data: LoginParams) {
  return request.post<unknown, LoginResult>('/auth/login', data)
}

export function refresh(refreshToken: string) {
  return request.post<unknown, LoginResult>('/auth/refresh', { refresh_token: refreshToken })
}

export function getMe() {
  return request.get<unknown, User>('/auth/me')
}

export function logout() {
  return request.post('/auth/logout')
}
