import dayjs from 'dayjs'

/**
 * 格式化金额（分转元）
 */
export function formatAmount(amount: number | undefined | null, decimals = 2): string {
  if (amount === undefined || amount === null) return '0.00'
  return Number(amount).toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

/**
 * 格式化日期
 */
export function formatDate(date: string | undefined | null): string {
  if (!date) return '-'
  return dayjs(date).format('YYYY-MM-DD')
}

/**
 * 格式化日期时间
 */
export function formatDateTime(date: string | undefined | null): string {
  if (!date) return '-'
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss')
}

/**
 * 格式化状态
 */
export function formatStatus(status: string): string {
  const statusMap: Record<string, string> = {
    // 企业状态
    pending: '待接入',
    configuring: '配置中',
    observing: '观察模式',
    simulating: '模拟运行',
    pending_approval: '待生产审批',
    active: '正常服务',
    suspended: '暂停开票',
    terminated: '已终止',
    archived: '已归档',
    // 任务状态
    pending_validation: '待校验',
    validation_passed: '校验通过',
    pending_submit: '待提交',
    queuing: '排队中',
    submitting: '提交中',
    accepted: '已受理',
    confirming: '确认中',
    success: '开票成功',
    failed: '开票失败',
    unknown: '结果未知',
    awaiting_reconciliation: '等待对账',
    awaiting_manual: '等待人工处理',
    terminated: '已终止',
    // 工作项状态
    in_progress: '处理中',
    resolved: '已解决',
    escalated: '已升级',
    // 异常状态
    open: '待处理',
    processing: '处理中',
    ignored: '已忽略'
  }
  return statusMap[status] || status
}

/**
 * 格式化百分比
 */
export function formatPercent(value: number | undefined | null, decimals = 1): string {
  if (value === undefined || value === null) return '0%'
  return `${Number(value).toFixed(decimals)}%`
}

/**
 * 格式化税率（后端存百分数 13 表示 13%）
 */
export function formatTaxRate(rate: number | string | undefined | null, decimals = 2): string {
  if (rate === undefined || rate === null || rate === '') return '0%'
  const n = Number(rate)
  if (Number.isNaN(n)) return '0%'
  return `${n.toFixed(decimals)}%`
}

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}
