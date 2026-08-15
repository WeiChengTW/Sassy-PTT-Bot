<template>
  <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
    <div class="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center text-3xl mb-3 shadow-inner">
      <span>{{ icon }}</span>
    </div>
    <h3 class="text-base font-bold text-slate-800">{{ title }}</h3>
    <p v-if="description" class="text-xs text-slate-400 mt-1 max-w-xs leading-relaxed">
      {{ description }}
    </p>
    <div v-if="$slots.action" class="mt-4">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    icon?: string
    title: string
    description?: string
  }>(),
  {
    icon: '✨',
  }
)
</script>
