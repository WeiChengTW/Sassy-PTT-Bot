<template>
  <div class="flex items-center justify-between mb-3 mt-6">
    <div class="flex items-center gap-2">
      <span v-if="icon" class="text-base">{{ icon }}</span>
      <h2 class="font-bold text-sm text-slate-700 tracking-wide">
        {{ title }}
      </h2>
      <span v-if="subtitle" class="text-xs font-normal text-slate-400">
        {{ subtitle }}
      </span>
    </div>
    <div v-if="$slots.action" class="flex items-center gap-1.5">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  icon?: string
  subtitle?: string
}>()
</script>
