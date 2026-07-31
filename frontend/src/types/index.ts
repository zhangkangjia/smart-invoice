// ========== 基础类型 ==========

export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

export interface PaginatedResponse<T = any> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface PaginationParams {
  page?: number
  page_size?: number
  [key: string]: any
}

// ========== 用户与权限 ==========

export interface User {
  id: string
  username: string
  full_name: string | null
  email: string | null
  phone: string | null
  status: string
  is_super_admin: boolean
  tenant_id: string
  created_at: string
  updated_at: string
}

export interface Role {
  id: string
  name: string
  code: string
  description: string | null
  permissions: string[]
}

// ========== 企业 ==========

export type EnterpriseStatus =
  | 'pending'
  | 'configuring'
  | 'observing'
  | 'simulating'
  | 'pending_approval'
  | 'active'
  | 'suspended'
  | 'terminated'
  | 'archived'

export interface Enterprise {
  id: string
  tenant_id: string
  name: string
  tax_no: string | null
  address: string | null
  phone: string | null
  bank_name: string | null
  bank_account: string | null
  status: EnterpriseStatus
  agency_id: string | null
  branch_id: string | null
  service_level: string | null
  created_at: string
  updated_at: string
}

export interface EnterpriseConfig {
  id: string
  enterprise_id: string
  invoice_types: string[]
  default_tax_rate: number | null
  single_amount_limit: number | null
  daily_limit: number | null
  max_concurrency: number
  auto_approve_threshold: number
  split_rules: any
  merge_rules: any
  remark_template: string | null
  enabled_time_windows: any
}

export interface ServiceAssignment {
  id: string
  enterprise_id: string
  user_id: string
  role: string
  start_at: string
  end_at: string | null
  assigned_by: string | null
  status: string
}

export interface EnterpriseHealth {
  enterprise_id: string
  health_score: number
  config_completeness: number
  title_coverage: number
  product_match_rate: number
  success_rate: number
  exception_count: number
  auto_process_rate: number
}

// ========== 客户 ==========

export interface CustomerTitle {
  id: string
  tenant_id: string
  enterprise_id: string
  name: string
  alias: string | null
  tax_no: string | null
  address: string | null
  phone: string | null
  bank_name: string | null
  bank_account: string | null
  email: string | null
  mobile: string | null
  status: string
  created_at: string
}

export interface CustomerContact {
  id: string
  tenant_id: string
  enterprise_id: string
  customer_title_id: string | null
  name: string
  mobile: string | null
  email: string | null
  is_primary: boolean
}

// ========== 商品规则 ==========

export interface ProductRule {
  id: string
  enterprise_id: string
  original_name: string
  aliases?: string[]
  standard_name: string
  tax_code?: string
  default_tax_rate?: number
  unit?: string
  spec?: string
  remark_template?: string
  status: string
  created_at: string
  updated_at?: string
}

// ========== 业务请求与发票 ==========

export interface BusinessRequest {
  id: string
  tenant_id: string
  enterprise_id: string
  source_type: 'text' | 'image' | 'excel' | 'api' | 'web_link'
  source_channel: string | null
  external_order_no: string | null
  contact_id: string | null
  customer_remark: string | null
  internal_remark: string | null
  urgency: 'low' | 'normal' | 'high' | 'urgent'
  expected_at: string | null
  current_handler_id: string | null
  current_stage: string | null
  status: string
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface SourceDocument {
  id: string
  business_request_id: string | null
  doc_type: string
  content: string | null
  file_name: string | null
  file_size: number | null
  file_hash: string | null
  ocr_result: any
  created_at: string
}

export type TaskStatus =
  | 'pending_validation'
  | 'validation_passed'
  | 'pending_submit'
  | 'queuing'
  | 'submitting'
  | 'accepted'
  | 'confirming'
  | 'success'
  | 'failed'
  | 'unknown'
  | 'awaiting_reconciliation'
  | 'awaiting_manual'
  | 'terminated'

export interface InvoiceRequest {
  id: string
  tenant_id: string
  enterprise_id: string
  business_request_id: string | null
  invoice_type: string
  buyer_name: string
  buyer_tax_no: string | null
  buyer_address: string | null
  buyer_phone: string | null
  buyer_bank_name: string | null
  buyer_bank_account: string | null
  is_tax_inclusive: boolean
  total_amount: number
  total_tax: number
  total_with_tax: number
  remark: string | null
  receiver_email: string | null
  receiver_mobile: string | null
  config_snapshot: any
  status: string
  created_at: string
  items?: InvoiceItem[]
}

export interface InvoiceItem {
  id: string
  invoice_request_id: string
  product_name: string
  tax_code: string | null
  spec: string | null
  unit: string | null
  quantity: number
  unit_price: number
  amount: number
  tax_rate: number
  tax_amount: number
  total_with_tax: number
  discount_amount: number | null
}

export interface InvoiceTask {
  id: string
  tenant_id: string
  enterprise_id: string
  invoice_request_id: string
  import_batch_id: string | null
  idempotency_key: string | null
  status: TaskStatus
  channel_submission_id: string | null
  worker_node: string | null
  retry_count: number
  max_retries: number
  last_error: string | null
  submitted_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface InvoiceResult {
  id: string
  invoice_task_id: string
  invoice_number: string | null
  invoice_code: string | null
  invoice_date: string | null
  total_amount: number | null
  total_tax: number | null
  total_with_tax: number | null
  buyer_name: string | null
  seller_name: string | null
  file_status: string
  file_key: string | null
  file_hash: string | null
  verified: boolean
  created_at: string
}

export interface ImportBatch {
  id: string
  tenant_id: string
  source_type: string
  created_by: string | null
  enterprise_count: number
  task_count: number
  success_count: number
  failure_count: number
  exception_count: number
  status: string
  file_name: string | null
  created_at: string
}

// ========== 工作项 ==========

export interface WorkItem {
  id: string
  tenant_id: string
  enterprise_id: string
  business_request_id: string | null
  work_type: string
  assigned_to: string | null
  collaborator_ids: string[]
  priority: 'low' | 'normal' | 'high' | 'urgent'
  deadline_at: string | null
  status: 'pending' | 'in_progress' | 'resolved' | 'cancelled' | 'escalated'
  exception_reason: string | null
  handling_note: string | null
  created_at: string
  updated_at: string
}

// ========== 异常 ==========

export interface ExceptionCase {
  id: string
  tenant_id: string
  enterprise_id: string
  invoice_task_id: string | null
  exception_type: string
  description: string
  auto_fixable: boolean
  affected_count: number
  status: 'open' | 'processing' | 'resolved' | 'ignored'
  resolved_by: string | null
  resolved_at: string | null
  created_at: string
}

// ========== 审计日志 ==========

export interface AuditLog {
  id: string
  tenant_id: string
  user_id: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  before_value: any
  after_value: any
  ip_address: string | null
  trace_id: string | null
  created_at: string
}

// ========== 统计 ==========

export interface DashboardStats {
  today_invoice_count: number
  success_rate: number
  pending_tasks: number
  exception_count: number
  total_amount: number
  week_trend?: TrendItem[]
  month_trend?: TrendItem[]
}

export interface TrendItem {
  date: string
  count: number
  amount: number
}

export interface EnterpriseStats {
  enterprise_id: string
  enterprise_name: string
  total_invoice_count: number
  success_count: number
  failed_count: number
  total_amount: number
  success_rate: number
  avg_processing_time: number
}

// ========== 组织 ==========

export interface Agency {
  id: string
  tenant_id: string
  name: string
  code: string
  status: string
}

export interface Branch {
  id: string
  tenant_id: string
  agency_id: string
  name: string
  code: string
  status: string
}

export interface Department {
  id: string
  tenant_id: string
  branch_id: string
  name: string
  code: string
  status: string
}

export interface Team {
  id: string
  tenant_id: string
  department_id: string
  name: string
  code: string
  status: string
}

// ========== AI 识别 ==========

export interface FieldExtraction {
  field_name: string
  value: any
  confidence: number
  source: 'ocr' | 'llm' | 'multimodal' | 'rule' | 'knowledge_base'
  position?: { page?: number; x?: number; y?: number; w?: number; h?: number }
  raw_text?: string
}

export interface RecognitionResult {
  success: boolean
  fields: FieldExtraction[]
  errors: string[]
  model_name: string
  model_version: string
  processing_time_ms: number
}

// ========== 通道 ==========

export interface ChannelCapability {
  supports_electronic_special: boolean
  supports_electronic_normal: boolean
  supports_special: boolean
  supports_normal: boolean
  supports_red_invoice: boolean
  supports_batch: boolean
  supports_split: boolean
  max_items_per_invoice: number
  max_amount: number
  requires_tax_no: boolean
}

export interface ChannelInfo {
  provider_code: string
  provider_name: string
  healthy: boolean
  capabilities: ChannelCapability
}

// ========== 批量操作 ==========

export interface BatchPreviewResult {
  total_count: number
  executable_count: number
  non_executable_count: number
  high_risk_count: number
  unknown_result_count: number
  requires_approval: boolean
  details: any[]
  non_executable_reasons: Record<string, number>
}

// ========== 提交链接 ==========

export interface SubmissionLink {
  id: string
  enterprise_id: string
  enterprise_name?: string
  token: string
  link_type: 'one_time' | 'permanent' | 'expiring'
  max_uses: number
  used_count: number
  expires_at: string | null
  is_active: boolean
  created_at: string
}

// ========== 通用选项 ==========

export interface SelectOption {
  label: string
  value: string | number
  color?: string
}
