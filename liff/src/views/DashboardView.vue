<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
          <span>📊 群組儀表板</span>
        </h1>
        <p v-if="data?.group_name" class="text-xs font-semibold text-brand-600 mt-0.5">
          {{ data.group_name }}
        </p>
      </div>
    </div>

    <!-- Skeleton Loading -->
    <div v-if="loading" class="space-y-6">
      <div class="grid grid-cols-2 gap-3">
        <div v-for="i in 4" :key="i" class="bg-white rounded-2xl p-4 border border-slate-100">
          <div class="skeleton h-4 w-14 rounded-full mb-3" />
          <div class="skeleton h-8 w-24 rounded-lg" />
        </div>
      </div>
      <div class="skeleton h-4 w-28 rounded-full" />
      <div class="bg-white rounded-2xl border border-slate-100 p-4 divide-y divide-slate-100">
        <div v-for="i in 5" :key="i" class="flex items-center py-3 gap-3">
          <div class="skeleton w-6 h-4 rounded" />
          <div class="skeleton flex-1 h-4 rounded-full" />
          <div class="skeleton w-12 h-4 rounded" />
        </div>
      </div>
    </div>

    <!-- Error State -->
    <EmptyState
      v-else-if="error"
      icon="⚠️"
      title="無法載入資料"
      :description="error"
    />

    <!-- Main Content -->
    <div v-else-if="data" class="space-y-6">
      <!-- Stat cards with Stagger Animation -->
      <div class="grid grid-cols-2 gap-3 stagger">
        <StatCard
          class="card-rise"
          label="總訊息量"
          :value="data.summary.total_messages"
          icon="💬"
          variant="brand"
        />
        <StatCard
          class="card-rise"
          label="群組成員"
          :value="data.summary.member_count"
          icon="👥"
          variant="success"
        />
        <StatCard
          class="card-rise"
          label="進行中旅行"
          :value="data.summary.active_trips"
          icon="🎒"
          variant="purple"
        />
        <StatCard
          class="card-rise"
          label="活躍天數"
          :value="data.summary.active_days"
          icon="🔥"
          variant="accent"
        />
      </div>

      <!-- 群組健康度 -->
      <template v-if="data.health">
        <div>
          <SectionHeader title="群組健康指數" icon="💓" />
          <BaseCard class="p-4 card-rise">
            <div class="flex items-center gap-4">
              <div class="text-center shrink-0 pl-2">
                <p class="text-4xl font-black tabular-nums font-mono text-brand-600 leading-none">
                  {{ data.health.overall }}
                </p>
                <p class="text-[11px] font-semibold text-slate-400 mt-1 uppercase tracking-wider">/ 100 分</p>
              </div>
              <div class="flex-1 min-w-0" style="max-height:180px">
                <Radar :data="healthRadarData" :options="healthRadarOptions" style="max-height:180px" />
              </div>
            </div>
            <ul v-if="data.health.suggestions?.length" class="mt-4 pt-3 border-t border-slate-100 space-y-1.5">
              <li v-for="s in data.health.suggestions" :key="s" class="text-xs text-slate-600 flex items-start gap-2">
                <span class="text-brand-500 font-bold shrink-0">💡</span>
                <span>{{ s }}</span>
              </li>
            </ul>
          </BaseCard>
        </div>
      </template>

      <!-- 活躍時段熱力圖 -->
      <template v-if="data.heatmap && data.heatmap.length">
        <div>
          <SectionHeader title="群組活躍時段分佈" icon="🕒" />
          <BaseCard class="p-4 card-rise">
            <HeatmapChart :data="data.heatmap" :date-data="data.recent_date_heatmap" />
          </BaseCard>
        </div>
      </template>

      <!-- 每週趨勢對比 -->
      <template v-if="weekly && weekly.weeks.length">
        <div>
          <SectionHeader title="每週發言趨勢" icon="📈" />
          <BaseCard class="p-4 card-rise">
            <div class="flex items-baseline gap-2 mb-3">
              <span class="text-2xl font-bold tabular-nums font-mono text-slate-800">
                {{ weekly.this_week.toLocaleString() }}
              </span>
              <span class="text-xs text-slate-400 font-medium">本週</span>
              <span
                v-if="weekly.growth_percent !== null"
                class="text-xs font-bold px-2 py-0.5 rounded-full inline-flex items-center gap-0.5"
                :class="weekly.growth_percent >= 0 ? 'bg-success-50 text-success-700' : 'bg-danger-50 text-danger-700'"
              >
                {{ weekly.growth_percent >= 0 ? '↑' : '↓' }} {{ Math.abs(weekly.growth_percent) }}%
              </span>
              <span class="text-xs text-slate-400 ml-auto tabular-nums font-medium">
                上週 {{ weekly.last_week.toLocaleString() }}
              </span>
            </div>
            <Bar :data="weeklyBarData" :options="weeklyOptions" style="max-height:160px" />
          </BaseCard>
        </div>
      </template>

      <!-- 月成長趨勢 -->
      <template v-if="data.monthly_trend && data.monthly_trend.length">
        <div>
          <SectionHeader title="月份成長軌跡" icon="📊" />
          <BaseCard class="p-4 card-rise">
            <Line :data="monthlyLineData" :options="monthlyOptions" style="max-height:180px" />
          </BaseCard>
          <div v-if="latestGrowth !== null" class="mt-2 text-xs text-slate-500 px-1 flex items-center justify-between">
            <span>最近一個月相對前月：</span>
            <span
              class="font-bold px-2 py-0.5 rounded-full"
              :class="latestGrowth >= 0 ? 'bg-success-50 text-success-700' : 'bg-danger-50 text-danger-700'"
            >
              {{ latestGrowth >= 0 ? '成長 ↑' : '減少 ↓' }} {{ Math.abs(latestGrowth) }}%
            </span>
          </div>
        </div>
      </template>

      <!-- 季節性 -->
      <template v-if="data.seasonality && data.seasonality.length">
        <div>
          <SectionHeader title="季節月份合計" icon="🍂" />
          <BaseCard class="p-4 card-rise">
            <Bar :data="seasonBarData" :options="seasonOptions" style="max-height:160px" />
          </BaseCard>
        </div>
      </template>

      <!-- 旅行類型分佈 -->
      <template v-if="data.trip_type_distribution && data.trip_type_distribution.length">
        <div>
          <SectionHeader title="旅行類型分佈" icon="🏕️" />
          <BaseCard class="p-4 flex flex-wrap gap-2 card-rise">
            <span
              v-for="d in data.trip_type_distribution"
              :key="d.type"
              class="inline-flex items-center gap-1.5 rounded-xl bg-slate-100 border border-slate-200/80 px-3 py-1.5 text-xs text-slate-700 font-medium"
            >
              <span>{{ emojiFor(d.type) }}</span>
              <span>{{ labelFor(d.type) }}</span>
              <span class="text-slate-400 font-mono text-[11px]">×{{ d.count }}</span>
            </span>
          </BaseCard>
        </div>
      </template>

      <!-- Top users -->
      <div>
        <SectionHeader title="Top 話癆榜" icon="🏆" />
        <BaseCard class="overflow-hidden card-rise">
          <div class="divide-y divide-slate-100">
            <div
              v-for="(u, i) in data.top_users.slice(0, 5)"
              :key="u.user_id"
              class="flex items-center px-4 py-3.5 gap-3 transition-colors hover:bg-slate-50/80"
              :class="i === 0 ? 'bg-accent-50/40' : ''"
            >
              <span
                class="text-sm w-6 text-center font-bold tabular-nums"
                :class="i === 0 ? 'text-accent-600' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-700' : 'text-slate-300 font-normal'"
              >
                {{ i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1 }}
              </span>
              <span class="flex-1 text-sm font-semibold text-slate-800 truncate">
                {{ u.user_name || u.user_id }}
              </span>
              <span class="text-sm font-bold font-mono tabular-nums text-slate-700">
                {{ u.total.toLocaleString() }}
                <span class="text-xs font-normal text-slate-400 ml-0.5">則</span>
              </span>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Message type breakdown -->
      <div>
        <SectionHeader title="訊息類型分佈" icon="🧩" />
        <BaseCard class="overflow-hidden card-rise">
          <div class="divide-y divide-slate-100">
            <div
              v-for="t in data.type_distribution"
              :key="t.type"
              class="flex items-center px-4 py-3 gap-3"
            >
              <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ background: TYPE_COLORS[t.type] || '#94a3b8' }" />
              <span class="flex-1 text-sm font-medium text-slate-700 capitalize">{{ t.type }}</span>
              <span class="text-sm font-semibold font-mono tabular-nums text-slate-600">
                {{ t.count.toLocaleString() }}
              </span>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Bar, Line, Radar } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, RadialLinearScale,
  BarElement, PointElement, LineElement, Tooltip, Legend, Filler,
} from 'chart.js'
import { api } from '@/api/client'
import { useRefreshOnAnalysis } from '@/composables/useRefreshOnAnalysis'
import { emojiFor, labelFor } from '@/constants/tripTypes'
import { TYPE_COLORS } from '@/constants/chartColors'
import HeatmapChart from '@/components/HeatmapChart.vue'
import BaseCard from '@/components/BaseCard.vue'
import StatCard from '@/components/StatCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import SectionHeader from '@/components/SectionHeader.vue'

ChartJS.register(CategoryScale, LinearScale, RadialLinearScale, BarElement, PointElement, LineElement, Tooltip, Legend, Filler)

const data = ref<any>(null)
const loading = ref(true)
const error = ref('')

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
      backgroundColor: 'rgba(99,102,241,0.12)',
      fill: true,
      tension: 0.35,
      borderWidth: 2.5,
      pointRadius: 3,
      pointBackgroundColor: '#6366f1',
    }],
  }
})

const monthlyOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { display: false } },
    y: { grid: { color: 'rgba(226,232,240,0.6)' } },
  },
}

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
      backgroundColor: '#818cf8',
      borderRadius: 6,
    }],
  }
})

const seasonOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { display: false } },
    y: { grid: { color: 'rgba(226,232,240,0.6)' } },
  },
}

const HEALTH_LABELS: Record<string, string> = {
  activity: '活躍度', diversity: '多樣性', sentiment: '正面情緒', participation: '參與度',
}

const healthRadarData = computed(() => {
  const h = data.value?.health
  if (!h) return { labels: [], datasets: [] }
  const keys = ['activity', 'diversity', 'sentiment', 'participation']
    .filter((k) => h[k] !== null && h[k] !== undefined)
  return {
    labels: keys.map((k) => HEALTH_LABELS[k]),
    datasets: [{
      data: keys.map((k) => h[k]),
      borderColor: '#6366f1',
      backgroundColor: 'rgba(99,102,241,0.2)',
      pointBackgroundColor: '#6366f1',
      pointBorderColor: '#fff',
      pointHoverBackgroundColor: '#fff',
      pointHoverBorderColor: '#6366f1',
      borderWidth: 2,
    }],
  }
})

const healthRadarOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: {
    r: {
      min: 0,
      max: 100,
      ticks: { stepSize: 25, display: false },
      grid: { color: 'rgba(226,232,240,0.8)' },
      angleLines: { color: 'rgba(226,232,240,0.8)' },
      pointLabels: { font: { size: 11, weight: 'bold' as const, family: 'Inter, Noto Sans TC' }, color: '#64748b' },
    },
  },
}

const weekly = computed(() => data.value?.weekly_trend || null)

const weeklyBarData = computed(() => {
  const w = weekly.value
  if (!w) return { labels: [], datasets: [] }
  return {
    labels: w.weeks.map((r: any) => r.week.split('-')[1] ? `W${r.week.split('-')[1]}` : r.week),
    datasets: [{
      data: w.weeks.map((r: any) => r.count),
      backgroundColor: w.weeks.map((_: any, i: number) =>
        i === w.weeks.length - 1 ? '#6366f1' : '#c7d2fe'),
      borderRadius: 6,
    }],
  }
})

const weeklyOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { display: false } },
    y: { grid: { color: 'rgba(226,232,240,0.6)' } },
  },
}

async function loadDashboard() {
  try { data.value = await api.dashboard() }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
}

onMounted(async () => {
  await loadDashboard()
  loading.value = false
})
useRefreshOnAnalysis(loadDashboard)
</script>
