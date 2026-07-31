<template>
  <div class="page-header">
    <div class="page-header__left">
      <h2 class="page-header__title">{{ title }}</h2>
      <p v-if="subtitle" class="page-header__subtitle">{{ subtitle }}</p>
    </div>
    <div class="page-header__right">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
}>()
</script>

<style scoped lang="scss">
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;

  &__left {
    flex: 1;
  }

  &__title {
    font-size: 20px;
    font-weight: 600;
    color: #1f2937;
    margin: 0;
  }

  &__subtitle {
    font-size: 13px;
    color: #6b7280;
    margin-top: 4px;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}
</style>
