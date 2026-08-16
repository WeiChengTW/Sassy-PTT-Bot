<template>
  <div class="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-slate-200/70 px-4 py-2 flex items-center gap-2.5 shadow-xs">
    <span class="text-xs font-semibold text-slate-500 shrink-0 flex items-center gap-1">
      <span>📅</span>
      <span>期間</span>
    </span>
    <select
      v-model="period" @change="onChange"
      class="flex-1 text-xs bg-slate-50/80 border border-slate-200 rounded-xl px-2.5 py-1.5 text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white transition-all cursor-pointer"
    >
      <option value="all">✨ 全部時間</option>
      <optgroup v-if="years.length" label="歷年">
        <option v-for="y in years" :key="y" :value="y">{{ y }} 年</option>
      </optgroup>
      <optgroup v-if="months.length" label="月份">
        <option v-for="m in months" :key="m" :value="m">{{ formatMonth(m) }}</option>
      </optgroup>
    </select>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, setPeriod, getPeriod } from '@/api/client'

const router = useRouter()
const period = ref(getPeriod())
const years = ref<string[]>([])
const months = ref<string[]>([])

function formatMonth(m: string) {
  const [y, mo] = m.split('-')
  return `${y} 年 ${parseInt(mo)} 月`
}

function onChange() {
  setPeriod(period.value)
  router.go(0)
}

onMounted(async () => {
  try {
    const data = await api.periods()
    years.value = data.years || []
    months.value = data.months || []
    // 若已存的選擇不在清單中，回退全部
    const valid = period.value === 'all'
      || years.value.includes(period.value)
      || months.value.includes(period.value)
    if (!valid) { period.value = 'all'; setPeriod('all') }
  } catch {}
})
</script>
