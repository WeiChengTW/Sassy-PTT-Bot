<template>
  <div
    class="rounded-2xl p-4 transition-all duration-200 border relative overflow-hidden"
    :class="variantClasses"
  >
    <div class="flex items-start justify-between">
      <div>
        <p class="text-xs font-semibold tracking-wide uppercase" :class="labelClasses">
          {{ label }}
        </p>
        <p class="text-2xl font-bold tabular-nums tracking-tight mt-1" :class="valueClasses">
          {{ formattedValue }}
        </p>
      </div>
      <div
        v-if="icon"
        class="w-10 h-10 rounded-xl flex items-center justify-center text-xl shrink-0"
        :class="iconBgClasses"
      >
        <span>{{ icon }}</span>
      </div>
    </div>
    <div v-if="subtext" class="mt-2 text-xs flex items-center gap-1" :class="subtextClasses">
      <slot name="subtext">{{ subtext }}</slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    label: string
    value: number | string
    icon?: string
    variant?: 'brand' | 'success' | 'accent' | 'info' | 'purple'
    subtext?: string
  }>(),
  {
    variant: 'brand',
  }
)

const formattedValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toLocaleString()
  }
  return props.value
})

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'success':
      return 'bg-gradient-to-br from-success-50/90 to-emerald-50/40 border-success-100/80 shadow-card hover:border-success-200'
    case 'accent':
      return 'bg-gradient-to-br from-accent-50/90 to-amber-50/40 border-accent-200/70 shadow-card hover:border-accent-300'
    case 'info':
      return 'bg-gradient-to-br from-info-50/90 to-sky-50/40 border-info-100/80 shadow-card hover:border-info-200'
    case 'purple':
      return 'bg-gradient-to-br from-purple-50/90 to-fuchsia-50/40 border-purple-100/80 shadow-card hover:border-purple-200'
    case 'brand':
    default:
      return 'bg-gradient-to-br from-brand-50/90 to-indigo-50/40 border-brand-100/80 shadow-card hover:border-brand-200'
  }
})

const labelClasses = computed(() => {
  switch (props.variant) {
    case 'success': return 'text-success-700'
    case 'accent': return 'text-accent-700'
    case 'info': return 'text-info-700'
    case 'purple': return 'text-purple-700'
    case 'brand':
    default: return 'text-brand-700'
  }
})

const valueClasses = computed(() => {
  switch (props.variant) {
    case 'success': return 'text-emerald-950'
    case 'accent': return 'text-amber-950'
    case 'info': return 'text-sky-950'
    case 'purple': return 'text-purple-950'
    case 'brand':
    default: return 'text-brand-900'
  }
})

const iconBgClasses = computed(() => {
  switch (props.variant) {
    case 'success': return 'bg-success-100 text-success-700'
    case 'accent': return 'bg-accent-100 text-accent-700'
    case 'info': return 'bg-info-100 text-info-700'
    case 'purple': return 'bg-purple-100 text-purple-700'
    case 'brand':
    default: return 'bg-brand-100 text-brand-700'
  }
})

const subtextClasses = computed(() => {
  switch (props.variant) {
    case 'success': return 'text-success-600/80'
    case 'accent': return 'text-accent-600/80'
    case 'info': return 'text-info-600/80'
    case 'purple': return 'text-purple-600/80'
    case 'brand':
    default: return 'text-brand-600/80'
  }
})
</script>
