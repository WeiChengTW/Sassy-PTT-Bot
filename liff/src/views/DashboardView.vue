<template>
  <div>
    <h1 class="text-xl font-bold mb-4 text-gray-900">
      群組儀表板
      <span v-if="data?.group_name" class="block text-sm font-normal text-gray-400 mt-0.5">{{ data.group_name }}</span>
    </h1>

    <!-- Skeleton -->
    <div v-if="loading">
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div v-for="i in 4" :key="i" class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
          <div class="skeleton h-8 w-16 rounded mb-2" />
          <div class="skeleton h-3 w-12 rounded-full" />
        </div>
      </div>
      <div class="skeleton h-4 w-24 rounded-full mb-3" />
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y">
        <div v-for="i in 5" :key="i" class="flex items-center px-4 py-3 gap-3">
          <div class="skeleton w-5 h-4 rounded" />
          <div class="skeleton flex-1 h-4 rounded-full" />
          <div class="skeleton w-10 h-4 rounded" />
        </div>
      </div>
    </div>

    <div v-else-if="error" class="flex flex-col items-center py-16 text-center gap-2">
      <p class="text-3xl">⚠️</p>
      <p class="text-sm font-medium text-gray-700">無法載入資料</p>
      <p class="text-xs text-gray-400">{{ error }}</p>
    </div>
    <div v-else-if="data">
      <!-- Stat cards -->
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="bg-blue-50 border border-blue-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-blue-700">
            {{ data.summary.total_messages.toLocaleString() }}
          </p>
          <p class="text-xs text-blue-500 mt-0.5">總訊息</p>
        </div>
        <div class="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-emerald-700">
            {{ data.summary.member_count }}
          </p>
          <p class="text-xs text-emerald-500 mt-0.5">成員數</p>
        </div>
        <div class="bg-violet-50 border border-violet-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-violet-700">
            {{ data.summary.active_trips }}
          </p>
          <p class="text-xs text-violet-500 mt-0.5">進行中旅行</p>
        </div>
        <div class="bg-amber-50 border border-amber-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-amber-700">
            {{ data.summary.active_days }}
          </p>
          <p class="text-xs text-amber-500 mt-0.5">活躍天數</p>
        </div>
      </div>

      <!-- 月成長趨勢 -->
      <template v-if="data.monthly_trend && data.monthly_trend.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">月成長趨勢</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-3">
          <Line :data="monthlyLineData" :options="monthlyOptions" style="max-height:180px" />
        </div>
        <div v-if="latestGrowth !== null" class="mb-6 text-xs text-gray-500 px-1">
          最近一個月相對前月
          <span :class="latestGrowth >= 0 ? 'text-emerald-600 font-semibold' : 'text-rose-500 font-semibold'">
            {{ latestGrowth >= 0 ? '↑' : '↓' }} {{ Math.abs(latestGrowth) }}%
          </span>
        </div>
      </template>

      <!-- 季節性 -->
      <template v-if="data.seasonality && data.seasonality.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">季節性（各月合計）</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
          <Bar :data="seasonBarData" :options="seasonOptions" style="max-height:160px" />
        </div>
      </template>

      <!-- 旅行類型分佈 -->
      <template v-if="data.trip_type_distribution && data.trip_type_distribution.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">旅行類型分佈</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6 flex flex-wrap gap-2">
          <span v-for="d in data.trip_type_distribution" :key="d.type"
                class="inline-flex items-center gap-1 rounded-full bg-violet-50 border border-violet-100 px-3 py-1 text-xs text-violet-700">
            {{ emojiFor(d.type) }} {{ labelFor(d.type) }}
            <span class="opacity-60 tabular-nums">×{{ d.count }}</span>
          </span>
        </div>
      </template>

      <!-- Top users -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">Top 話癆</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y mb-6 overflow-hidden">
        <div v-for="(u, i) in data.top_users.slice(0, 5)" :key="u.user_id"
             class="flex items-center px-4 py-3 gap-3">
          <span class="text-gray-300 text-sm w-5 tabular-nums font-medium">{{ i + 1 }}</span>
          <span class="flex-1 text-sm text-gray-800 truncate">{{ u.user_name || u.user_id }}</span>
          <span class="text-sm font-semibold tabular-nums text-gray-700">{{ u.total.toLocaleString() }}</span>
        </div>
      </div>

      <!-- Message type breakdown -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">訊息類型</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y overflow-hidden">
        <div v-for="t in data.type_distribution" :key="t.type"
             class="flex items-center px-4 py-3 gap-3">
          <span class="w-2 h-2 rounded-full flex-shrink-0" :style="{ background: TYPE_COLORS[t.type] || '#94a3b8' }" />
          <span class="flex-1 text-sm text-gray-700 capitalize">{{ t.type }}</span>
          <span class="text-sm font-semibold tabular-nums text-gray-600">{{ t.count.toLocaleString() }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Bar, Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale,
  BarElement, PointElement, LineElement, Tooltip, Legend, Filler,
} from 'chart.js'
import { api } from '@/api/client'
import { emojiFor, labelFor } from '@/constants/tripTypes'

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Tooltip, Legend, Filler)

const data = ref<any>(null)
const loading = ref(true)
const error = ref('')

const TYPE_COLORS: Record<string, string> = {
  text: '#60a5fa', sticker: '#f472b6', image: '#34d399',
  video: '#fb923c', audio: '#a78bfa', file: '#94a3b8',
}

const MONTH_LABELS = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']

const monthlyLineData = computed(() => {
  if (!data.value?.monthly_trend) return { labels: [], datasets: [] }
  const rows = data.value.monthly_trend
  return {
    labels: rows.map((r: any) => r.month),
    datasets: [{
      label: '訊息數',
      data: rows.map((r: any) => r.count),
      borderColor: '#6366f1',
      backgroundColor: 'rgba(99,102,241,0.1)',
      fill: true,
      tension: 0.35,
    }],
  }
})

const monthlyOptions = { responsive: true, plugins: { legend: { display: false } } }

const latestGrowth = computed(() => {
  const rows = data.value?.monthly_trend
  if (!rows || !rows.length) return null
  return rows[rows.length - 1].growth_rate_percent
})

const seasonBarData = computed(() => {
  if (!data.value?.seasonality) return { labels: [], datasets: [] }
  const map: Record<number, number> = {}
  data.value.seasonality.forEach((r: any) => { map[r.month] = r.count })
  return {
    labels: MONTH_LABELS,
    datasets: [{
      data: MONTH_LABELS.map((_, i) => map[i + 1] || 0),
      backgroundColor: '#fbbf24',
    }],
  }
})

const seasonOptions = { responsive: true, plugins: { legend: { display: false } } }

onMounted(async () => {
  try { data.value = await api.dashboard() }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
})
</script>
