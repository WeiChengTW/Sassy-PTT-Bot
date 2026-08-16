<template>
  <div
    class="rounded-2xl p-4 transition-all duration-300 border relative overflow-hidden group hover:shadow-lift"
    :class="variantClasses"
  >
    <!-- Background subtle ambient glow on top right -->
    <div class="absolute -top-6 -right-6 w-20 h-20 rounded-full opacity-20 blur-xl pointer-events-none" :class="glowClasses" />

    <div class="flex items-start justify-between relative z-10">
      <div>
        <p class="text-[11px] font-bold tracking-wider uppercase" :class="labelClasses">
          {{ label }}
        </p>
        <p class="text-2xl font-black font-mono tracking-tight mt-1.5" :class="valueClasses">
          <CountUp v-if="typeof value === 'number'" :value="value" :duration="700" />
          <span v-else>{{ value }}</span>
        </p>
      </div>
      <div
        v-if="icon"
        class="w-10 h-10 rounded-2xl flex items-center justify-center text-xl shrink-0 shadow-inner border border-white/60 transition-transform duration-200 group-hover:scale-110"
        :class="iconBgClasses"
      >
        <span>{{ icon }}</span>
      </div>
    </div>
    <div v-if="subtext" class="mt-2 text-xs flex items-center gap-1 font-medium relative z-10" :class="subtextClasses">
      <slot name="subtext">{{ subtext }}</slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CountUp from '@/components/CountUp.vue'

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

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'success':
      return 'bg-gradient-to-br from-success-50/95 via-white to-emerald-50/30 border-success-200/80 shadow-card hover:border-success-300'
    case 'accent':
      return 'bg-gradient-to-br from-accent-50/95 via-white to-amber-50/30 border-accent-200/80 shadow-card hover:border-accent-300'
    case 'info':
      return 'bg-gradient-to-br from-info-50/95 via-white to-sky-50/30 border-info-200/80 shadow-card hover:border-info-300'
    case 'purple':
      return 'bg-gradient-to-br from-purple-50/95 via-white to-fuchsia-50/30 border-purple-200/80 shadow-card hover:border-purple-300'
    case 'brand':
    default:
      return 'bg-gradient-to-br from-brand-50/95 via-white to-indigo-50/30 border-brand-200/80 shadow-card hover:border-brand-300'
  }
})

const glowClasses = computed(() => {
  switch (props.variant) {
    case 'success': return 'bg-emerald-500'
    case 'accent': return 'bg-amber-500'
    case 'info': return 'bg-sky-500'
    case 'purple': return 'bg-purple-500'
    case 'brand':
    default: return 'bg-brand-500'
  }
})

const labelClasses = computed(() => {
  switch (props.variant) {
    case 'success': return 'text-emerald-700'
    case 'accent': return 'text-amber-700'
    case 'info': return 'text-sky-700'
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
    default: return 'text-brand-950'
  }
})

const iconBgClasses = computed(() => {
  switch (props.variant) {
    case 'success': return 'bg-success-100/80 text-success-700'
    case 'accent': return 'bg-accent-100/80 text-accent-700'
    case 'info': return 'bg-info-100/80 text-info-700'
    case 'purple': return 'bg-purple-100/80 text-purple-700'
    case 'brand':
    default: return 'bg-brand-100/80 text-brand-700'
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
