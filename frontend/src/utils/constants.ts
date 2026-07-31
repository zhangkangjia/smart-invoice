import type { SelectOption } from '@/types'

export const ENTERPRISE_STATUS_OPTIONS: SelectOption[] = [
  { label: '待接入', value: 'pending', color: '#909399' },
  { label: '配置中', value: 'configuring', color: '#E6A23C' },
  { label: '观察模式', value: 'observing', color: '#409EFF' },
  { label: '模拟运行', value: 'simulating', color: '#409EFF' },
  { label: '待生产审批', value: 'pending_approval', color: '#E6A23C' },
  { label: '正常服务', value: 'active', color: '#67C23A' },
  { label: '暂停开票', value: 'suspended', color: '#F56C6C' },
  { label: '已终止', value: 'terminated', color: '#909399' },
  { label: '已归档', value: 'archived', color: '#C0C4CC' }
]

export const TASK_STATUS_OPTIONS: SelectOption[] = [
  { label: '待校验', value: 'pending_validation', color: '#909399' },
  { label: '校验通过', value: 'validation_passed', color: '#409EFF' },
  { label: '待提交', value: 'pending_submit', color: '#E6A23C' },
  { label: '排队中', value: 'queuing', color: '#409EFF' },
  { label: '提交中', value: 'submitting', color: '#409EFF' },
  { label: '已受理', value: 'accepted', color: '#409EFF' },
  { label: '确认中', value: 'confirming', color: '#E6A23C' },
  { label: '开票成功', value: 'success', color: '#67C23A' },
  { label: '开票失败', value: 'failed', color: '#F56C6C' },
  { label: '结果未知', value: 'unknown', color: '#E6A23C' },
  { label: '等待对账', value: 'awaiting_reconciliation', color: '#E6A23C' },
  { label: '等待人工处理', value: 'awaiting_manual', color: '#F56C6C' },
  { label: '已终止', value: 'terminated', color: '#909399' }
]

export const WORK_ITEM_TYPE_OPTIONS: SelectOption[] = [
  { label: '数据修正', value: 'data_correction', color: '#409EFF' },
  { label: '规则冲突', value: 'rule_conflict', color: '#F56C6C' },
  { label: '审批', value: 'approval', color: '#E6A23C' },
  { label: '重试', value: 'retry', color: '#409EFF' },
  { label: '交付', value: 'delivery', color: '#67C23A' },
  { label: '通道异常', value: 'channel_error', color: '#F56C6C' },
  { label: '补充资料', value: 'supplement', color: '#E6A23C' }
]

export const EXCEPTION_TYPE_OPTIONS: SelectOption[] = [
  { label: '购方资料缺失', value: 'buyer_missing', color: '#F56C6C' },
  { label: '税号识别失败', value: 'tax_no_failed', color: '#F56C6C' },
  { label: '商品编码未匹配', value: 'product_unmatched', color: '#E6A23C' },
  { label: '税率冲突', value: 'tax_rate_conflict', color: '#E6A23C' },
  { label: '金额不一致', value: 'amount_mismatch', color: '#F56C6C' },
  { label: '疑似重复开票', value: 'duplicate_suspect', color: '#F56C6C' },
  { label: '额度不足', value: 'quota_exceeded', color: '#E6A23C' },
  { label: '授权失效', value: 'auth_expired', color: '#F56C6C' },
  { label: '通道超时', value: 'channel_timeout', color: '#E6A23C' },
  { label: '图片不清晰', value: 'image_unclear', color: '#909399' },
  { label: '图片归组失败', value: 'group_failed', color: '#909399' }
]

export const PRIORITY_OPTIONS: SelectOption[] = [
  { label: '低', value: 'low', color: '#909399' },
  { label: '普通', value: 'normal', color: '#409EFF' },
  { label: '高', value: 'high', color: '#E6A23C' },
  { label: '紧急', value: 'urgent', color: '#F56C6C' }
]

export const SERVICE_LEVEL_OPTIONS: SelectOption[] = [
  { label: '普通', value: 'normal' },
  { label: '重点', value: 'key' },
  { label: 'VIP', value: 'vip' }
]

export const URGENCY_OPTIONS: SelectOption[] = [
  { label: '低', value: 'low', color: '#909399' },
  { label: '普通', value: 'normal', color: '#409EFF' },
  { label: '高', value: 'high', color: '#E6A23C' },
  { label: '紧急', value: 'urgent', color: '#F56C6C' }
]

export const INVOICE_TYPE_OPTIONS: SelectOption[] = [
  { label: '数电专票', value: 'electronic_special' },
  { label: '数电普票', value: 'electronic_normal' },
  { label: '增值税专票', value: 'special' },
  { label: '增值税普票', value: 'normal' }
]
