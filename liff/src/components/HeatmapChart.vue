<template>
  <div>
    <!-- 模式切換：週期常態 (週一～週日) vs 近期每日 (MM/DD) -->
    <div class="flex items-center justify-between mb-3">
      <span class="text-xs font-semibold text-gray-500">時段活躍分佈</span>
      <div class="flex rounded-lg bg-gray-100 p-0.5 border border-gray-200 text-xs">
        <button type="button" @click="viewMode = 'dates'"
                class="px-2.5 py-0.5 rounded-md font-medium transition-all"
                :class="viewMode === 'dates' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-800'">
          每日熱力
        </button>
        <button type="button" @click="viewMode = 'weekly'"
                class="px-2.5 py-0.5 rounded-md font-medium transition-all"
                :class="viewMode === 'weekly' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-800'">
          週期常態
        </button>
      </div>
    </div>

    <!-- 每日熱力視圖 (MM/DD HH:00) -->
    <div v-if="viewMode === 'dates'" class="overflow-x-auto -mx-1 px-1">
      <div class="inline-block min-w-full">
        <!-- Hour axis -->
        <div class="flex mb-1 pl-12">
          <span v-for="h in 24" :key="h"
                class="text-[8px] text-gray-300 text-center tabular-nums"
                :style="cellStyle">{{ (h - 1) % 6 === 0 ? h - 1 : '' }}</span>
        </div>
        <!-- Rows by recent dates -->
        <div v-for="row in dateRows" :key="row.date" class="flex items-center mb-0.5">
          <span class="text-[10px] text-gray-400 w-12 shrink-0 font-medium tabular-nums">{{ row.label }}</span>
          <span v-for="h in 24" :key="h"
                class="rounded-sm cursor-pointer"
                :style="dateCellColor(row.date, h - 1)"
                :title="`${row.label} ${h - 1}:00 · ${dateCountAt(row.date, h - 1)} 則`" />
        </div>
      </div>
    </div>

    <!-- 週期常態視圖 (週一～週日) -->
    <div v-else class="overflow-x-auto -mx-1 px-1">
      <div class="inline-block min-w-full">
        <!-- Hour axis -->
        <div class="flex mb-1 pl-6">
          <span v-for="h in 24" :key="h"
                class="text-[8px] text-gray-300 text-center tabular-nums"
                :style="cellStyle">{{ (h - 1) % 6 === 0 ? h - 1 : '' }}</span>
        </div>
        <!-- Rows by day of week -->
        <div v-for="row in weeklyRows" :key="row.dow" class="flex items-center mb-0.5">
          <span class="text-[9px] text-gray-400 w-6 shrink-0">{{ row.label }}</span>
          <span v-for="h in 24" :key="h"
                class="rounded-sm cursor-pointer"
                :style="weeklyCellColor(row.dow, h - 1)"
                :title="`週${row.label} ${h - 1}:00 · ${weeklyCountAt(row.dow, h - 1)} 則`" />
        </div>
      </div>
    </div>

    <div class="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 px-1">
      <span v-if="peak">
        巔峰時段：<span class="font-semibold text-gray-700">{{ peak.label }} {{ peak.hour }}:00</span>
        <span class="opacity-60 tabular-nums">（{{ peak.count }} 則）</span>
      </span>
      <span>
        夜貓子指數：<span class="text-amber-500">{{ '⭐'.repeat(nightStars) || '—' }}</span>
        <span class="opacity-60 tabular-nums">{{ nightPct }}% 在 22:00–04:00</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Cell { day_of_week: number; hour: number; count: number }
interface DateCell { date: string; hour: number; count: number }

const props = defineProps<{
  data: Cell[]
  dateData?: DateCell[]
}>()

const viewMode = ref<'dates' | 'weekly'>('dates')

// strftime %w：0=週日。以「一二三四五六日」順序顯示。
const weeklyRows = [
  { dow: 1, label: '一' }, { dow: 2, label: '二' }, { dow: 3, label: '三' },
  { dow: 4, label: '四' }, { dow: 5, label: '五' }, { dow: 6, label: '六' },
  { dow: 0, label: '日' },
]

const cellStyle = { width: '13px', minWidth: '13px', height: '13px' } as const

// --- 每日視圖邏輯 ---
const dateRows = computed(() => {
  const dates = [...new Set((props.dateData || []).map((d) => d.date))]
  // 最多取最近 14 天
  return dates.slice(0, 14).map((d) => {
    const parts = d.split('-')
    const label = parts.length >= 3 ? `${parts[1]}/${parts[2]}` : d
    return { date: d, label }
  })
})

const dateGrid = computed(() => {
  const m = new Map<string, number>()
  for (const c of props.dateData || []) m.set(`${c.date}-${c.hour}`, c.count)
  return m
})

const maxDateCount = computed(() =>
  Math.max(1, ...(props.dateData || []).map((c) => c.count)))

function dateCountAt(date: string, hour: number) {
  return dateGrid.value.get(`${date}-${hour}`) || 0
}

function dateCellColor(date: string, hour: number) {
  const v = dateCountAt(date, hour)
  const alpha = v === 0 ? 0 : 0.12 + 0.88 * (v / maxDateCount.value)
  return {
    ...cellStyle,
    backgroundColor: v === 0 ? '#f1f5f9' : `rgba(99,102,241,${alpha.toFixed(3)})`,
    marginRight: '2px',
  }
}

// --- 週期常態視圖邏輯 ---
const weeklyGrid = computed(() => {
  const m = new Map<string, number>()
  for (const c of props.data || []) m.set(`${c.day_of_week}-${c.hour}`, c.count)
  return m
})

const maxWeeklyCount = computed(() =>
  Math.max(1, ...(props.data || []).map((c) => c.count)))

function weeklyCountAt(dow: number, hour: number) {
  return weeklyGrid.value.get(`${dow}-${hour}`) || 0
}

function weeklyCellColor(dow: number, hour: number) {
  const v = weeklyCountAt(dow, hour)
  const alpha = v === 0 ? 0 : 0.12 + 0.88 * (v / maxWeeklyCount.value)
  return {
    ...cellStyle,
    backgroundColor: v === 0 ? '#f1f5f9' : `rgba(99,102,241,${alpha.toFixed(3)})`,
    marginRight: '2px',
  }
}

const peak = computed(() => {
  let best: { dow: number; hour: number; count: number } | null = null
  for (const c of props.data || []) {
    if (!best || c.count > best.count) best = { dow: c.day_of_week, hour: c.hour, count: c.count }
  }
  if (!best) return null
  const label = weeklyRows.find((r) => r.dow === best!.dow)?.label ?? ''
  return { label: `週${label}`, hour: best.hour, count: best.count }
})

const nightPct = computed(() => {
  const total = (props.data || []).reduce((s, c) => s + c.count, 0)
  if (!total) return 0
  const night = (props.data || [])
    .filter((c) => c.hour >= 22 || c.hour < 4)
    .reduce((s, c) => s + c.count, 0)
  return Math.round((night / total) * 100)
})

const nightStars = computed(() => Math.min(5, Math.round(nightPct.value / 20)))
</script>
