<template>
  <div class="flex flex-wrap gap-2">
    <button
      v-if="showAll"
      type="button"
      @click="$emit('update:modelValue', '')"
      class="rounded-full px-3 py-1.5 text-xs font-semibold border transition-all duration-150 btn-press"
      :class="
        modelValue === ''
          ? 'bg-brand-600 text-white border-brand-600 shadow-sm'
          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
      "
    >
      {{ allLabel }}
    </button>
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      @click="$emit('update:modelValue', opt.value)"
      class="rounded-full px-3 py-1.5 text-xs font-semibold border transition-all duration-150 btn-press inline-flex items-center gap-1"
      :class="
        modelValue === opt.value
          ? 'bg-brand-600 text-white border-brand-600 shadow-sm'
          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
      "
    >
      <span v-if="opt.emoji">{{ opt.emoji }}</span>
      <span>{{ opt.label }}</span>
      <span
        v-if="opt.count !== undefined"
        class="text-[10px] opacity-75 font-normal ml-0.5"
      >
        ({{ opt.count }})
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
export interface ChipOption {
  value: string
  label: string
  emoji?: string
  count?: number
}

withDefaults(
  defineProps<{
    modelValue: string
    options: ChipOption[]
    showAll?: boolean
    allLabel?: string
  }>(),
  {
    showAll: true,
    allLabel: '全部',
  }
)

defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()
</script>
