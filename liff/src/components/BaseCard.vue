<template>
  <div
    class="rounded-2xl transition-all duration-200"
    :class="[
      variantClasses,
      interactive ? 'btn-press cursor-pointer hover:shadow-lift' : '',
    ]"
  >
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 'surface' | 'brand' | 'subtle' | 'elevated'
    interactive?: boolean
  }>(),
  {
    variant: 'surface',
    interactive: false,
  }
)

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'brand':
      return 'bg-gradient-to-br from-brand-50 to-white border border-brand-100 shadow-card'
    case 'subtle':
      return 'bg-slate-50 border border-slate-200/70 shadow-none'
    case 'elevated':
      return 'bg-white border border-slate-100 shadow-lift'
    case 'surface':
    default:
      return 'bg-white border border-slate-200/80 shadow-card'
  }
})
</script>
