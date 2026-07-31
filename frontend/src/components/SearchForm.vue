<template>
  <el-card class="search-form" shadow="never">
    <el-form :model="formModel" inline @submit.prevent="handleSearch">
      <slot name="default" :form="formModel" />
      <el-form-item>
        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon>
          搜索
        </el-button>
        <el-button @click="handleReset">
          <el-icon><Refresh /></el-icon>
          重置
        </el-button>
        <slot name="extra" />
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'

const props = defineProps<{
  modelValue: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, any>): void
  (e: 'search', value: Record<string, any>): void
  (e: 'reset'): void
}>()

const formModel = reactive({ ...props.modelValue })

watch(
  () => props.modelValue,
  (val) => {
    Object.assign(formModel, val)
  },
  { deep: true }
)

function handleSearch() {
  emit('update:modelValue', { ...formModel })
  emit('search', { ...formModel })
}

function handleReset() {
  Object.keys(formModel).forEach((key) => {
    formModel[key] = ''
  })
  emit('update:modelValue', { ...formModel })
  emit('reset')
}
</script>

<style scoped lang="scss">
.search-form {
  margin-bottom: 16px;
  :deep(.el-card__body) {
    padding: 18px 20px 0 20px;
  }
  :deep(.el-form-item) {
    margin-bottom: 18px;
  }
}
</style>
