<template>
  <div class="space-y-3">
    <!-- 模式切換：週期常態 (週一～週日) vs 近期每日 (MM/DD) -->
    <div class="flex items-center justify-between">
      <span class="text-xs font-bold text-slate-700">活躍時段分佈熱力</span>
      <div class="flex rounded-xl bg-slate-100 p-0.5 border border-slate-200/80 text-xs">
        <button
          type="button"
          @click="viewMode = 'dates'"
          class="px-2.5 py-1 rounded-lg font-bold transition-all btn-press"
          :class="viewMode === 'dates' ? 'bg-white text-brand-600 shadow-sm' : 'text-slate-500 hover:text-slate-800'"
        >
          每日熱力
        </button>
        <button
          type="button"
          @click="viewMode = 'weekly'"
          class="px-2.5 py-1 rounded-lg font-bold transition-all btn-press"
          :class="viewMode === 'weekly' ? 'bg-white text-brand-600 shadow-sm' : 'text-slate-500 hover:text-slate-800'"
        >
          週期常態
        </button>
      </div>
    </div>

    <!-- 每日熱力視圖 (MM/DD HH:00) -->
    <div v-if="viewMode === 'dates'" class="overflow-x-auto -mx-1 px-1 no-scrollbar">
      <div class="inline-block min-w-full">
        <!-- Hour axis -->
        <div class="flex mb-1.5 pl-12">
          <span
            v-for="h in 24"
            :key="h"
            class="text-[9px] text-slate-400 font-mono text-center tabular-nums"
            :style="cellStyle"
          >
            {{ (h - 1) % 6 === 0 ? h - 1 : '' }}
          </span>
        </div>
        <!-- Rows by recent dates -->
        <div v-for="row in dateRows" :key="row.date" class="flex items-center mb-1">
          <span class="text-[10px] text-slate-500 w-12 shrink-0 font-bold font-mono tabular-nums">{{ row.label }}</span>
          <span
            v-for="h in 24"
            :key="h"
            class="rounded-sm cursor-pointer transition-transform hover:scale-125"
            :style="dateCellColor(row.date, h - 1)"
            :title="`${row.label} ${h - 1}:00 · ${dateCountAt(row.date, h - 1)} 則`"
          />
        </div>
      </div>
    </div>

    <!-- 週期常態視圖 (週一～週日) -->
    <div v-else class="overflow-x-auto -mx-1 px-1 no-scrollbar">
      <div class="inline-block min-w-full">
        <!-- Hour axis -->
        <div class="flex mb-1.5 pl-8">
          <span
            v-for="h in 24"
            :key="h"
            class="text-[9px] text-slate-400 font-mono text-center tabular-nums"
            :style="cellStyle"
          >
            {{ (h - 1) % 6 === 0 ? h - 1 : '' }}
          </span>
        </div>
        <!-- Rows by day of week -->
        <div v-for="row in weeklyRows" :key="row.dow" class="flex items-center mb-1">
          <span class="text-[10px] text-slate-500 w-8 shrink-0 font-bold">週{{ row.label }}</span>
          <span
            v-for="h in 24"
            :key="h"
            class="rounded-sm cursor-pointer transition-transform hover:scale-125"
            :style="weeklyCellColor(row.dow, h - 1)"
            :title="`${recentDowDate(row.dow)} 週${row.label} ${h - 1}:00 · ${weeklyCountAt(row.dow, h - 1)} 則`"
          />
        </div>
      </div>
    </div>

    <div class="mt-4 pt-3 border-t border-slate-100 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-slate-500">
      <span v-if="peak">
        🔥 巔峰時段：<span class="font-bold text-slate-800">{{ peak.label }} {{ peak.hour }}:00</span>
        <span class="opacity-75 font-mono">（{{ peak.count }} 則）</span>
      </span>
      <span>
        🌙 夜貓指數：<span class="text-amber-500 font-bold">{{ '⭐'.repeat(nightStars) || '—' }}</span>
        <span class="opacity-75 font-mono ml-1">{{ nightPct }}% 深夜發言</span>
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

const weeklyRows = [
  { dow: 1, label: '一' }, { dow: 2, label: '二' }, { dow: 3, label: '三' },
  { dow: 4, label: '四' }, { dow: 5, label: '五' }, { dow: 6, label: '六' },
  { dow: 0, label: '日' },
]

function recentDowDate(dow: number): string {
  const now = new Date()
  let diff = dow - now.getDay()  // getDay(): 0=日 … 6=六
  if (diff > 0) diff -= 7        // 往回找，確保日期不超過今天
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + diff)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${mm}/${dd}`
}

const cellStyle = { width: '13px', minWidth: '13px', height: '13px' } as const

const dateRows = computed(() => {
  const dates = [...new Set((props.dateData || []).map((d) => d.date))]
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

const dateMaxMap = computed(() => {
  const m = new Map<string, number>()
  for (const c of props.dateData || []) {
    m.set(c.date, Math.max(m.get(c.date) || 0, c.count))
  }
  return m
})

function dateCountAt(date: string, hour: number) {
  return dateGrid.value.get(`${date}-${hour}`) || 0
}

function dateCellColor(date: string, hour: number) {
  const v = dateCountAt(date, hour)
  const dayMax = dateMaxMap.value.get(date) || 1
  const alpha = v === 0 ? 0 : 0.15 + 0.85 * (v / dayMax)
  return {
    ...cellStyle,
    backgroundColor: v === 0 ? '#f1f5f9' : `rgba(99,102,241,${alpha.toFixed(3)})`,
    marginRight: '2px',
  }
}

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
  const alpha = v === 0 ? 0 : 0.15 + 0.85 * (v / maxWeeklyCount.value)
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
