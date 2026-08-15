<template>
  <div class="sticky top-0 z-20 bg-white/90 backdrop-blur-sm border-b border-gray-100 px-4 py-2 flex items-center gap-2">
    <span class="text-xs font-medium text-gray-400 shrink-0">📅 期間</span>
    <select
      v-model="period" @change="onChange"
      class="flex-1 text-xs bg-gray-50 border border-gray-200 rounded-lg px-2 py-1.5 text-gray-700 focus:outline-none focus:border-blue-300"
    >
      <option value="all">全部</option>
      <optgroup v-if="years.length" label="年">
        <option v-for="y in years" :key="y" :value="y">{{ y }} 年</option>
      </optgroup>
      <optgroup v-if="months.length" label="月">
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
