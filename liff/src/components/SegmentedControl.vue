<template>
  <div class="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200/80">
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      @click="$emit('update:modelValue', opt.value)"
      class="px-3 py-1 text-xs font-semibold rounded-lg transition-all duration-200 btn-press"
      :class="
        modelValue === opt.value
          ? 'bg-white text-brand-600 shadow-sm'
          : 'text-slate-500 hover:text-slate-800'
      "
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
export interface SegmentOption {
  value: string
  label: string
}

defineProps<{
  modelValue: string
  options: SegmentOption[]
}>()

defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()
</script>
