<template>
  <el-tag :type="tagType" :color="customColor" effect="light" size="small">
    {{ label }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  ENTERPRISE_STATUS_OPTIONS,
  TASK_STATUS_OPTIONS,
  WORK_ITEM_TYPE_OPTIONS,
  EXCEPTION_TYPE_OPTIONS,
  PRIORITY_OPTIONS
} from '@/utils/constants'
import { formatStatus } from '@/utils/format'

const props = defineProps<{
  status: string
  type?: 'enterprise' | 'task' | 'work-item' | 'exception' | 'priority'
}>()

const optionMap = computed(() => {
  switch (props.type) {
    case 'enterprise':
      return ENTERPRISE_STATUS_OPTIONS
    case 'task':
      return TASK_STATUS_OPTIONS
    case 'work-item':
      return WORK_ITEM_TYPE_OPTIONS
    case 'exception':
      return EXCEPTION_TYPE_OPTIONS
    case 'priority':
      return PRIORITY_OPTIONS
    default:
      return []
  }
})

const currentOption = computed(() => {
  return optionMap.value.find((opt) => opt.value === props.status)
})

const label = computed(() => {
  if (currentOption.value) return currentOption.value.label
  return formatStatus(props.status)
})

const tagType = computed<'primary' | 'success' | 'warning' | 'danger' | 'info'>(() => {
  const color = currentOption.value?.color || ''
  if (color.includes('67C23A') || color.includes('green')) return 'success'
  if (color.includes('E6A23C') || color.includes('orange')) return 'warning'
  if (color.includes('F56C6C') || color.includes('red')) return 'danger'
  if (color.includes('409EFF') || color.includes('blue')) return 'primary'
  return 'info'
})

const customColor = computed(() => {
  return undefined
})
</script>
