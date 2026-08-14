<template>
  <div>
    <h1 class="text-xl font-bold mb-4 text-gray-900">排行榜</h1>

    <!-- Skeleton -->
    <div v-if="loading">
      <div class="skeleton h-4 w-24 rounded-full mb-3" />
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y mb-6">
        <div v-for="i in 5" :key="i" class="flex items-center px-4 py-3 gap-3">
          <div class="skeleton w-6 h-4 rounded" />
          <div class="skeleton flex-1 h-4 rounded-full" />
          <div class="skeleton w-12 h-4 rounded" />
        </div>
      </div>
      <div class="skeleton h-4 w-36 rounded-full mb-3" />
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y">
        <div v-for="i in 3" :key="i" class="flex items-center px-4 py-3 gap-3">
          <div class="skeleton w-5 h-4 rounded" />
          <div class="skeleton flex-1 h-4 rounded-full" />
          <div class="skeleton w-12 h-4 rounded" />
        </div>
      </div>
    </div>

    <div v-else-if="error" class="flex flex-col items-center py-16 text-center gap-2">
      <p class="text-3xl">⚠️</p>
      <p class="text-sm font-medium text-gray-700">無法載入資料</p>
      <p class="text-xs text-gray-400">{{ error }}</p>
    </div>
    <div v-else-if="data">
      <!-- 活躍度排行 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">活躍度排行</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y mb-6 overflow-hidden">
        <div v-for="(u, i) in data.rankings" :key="u.user_id"
             class="flex items-center px-4 py-3 gap-3"
             :class="i === 0 ? 'bg-amber-50' : i === 1 ? 'bg-slate-50' : ''">
          <!-- Medal / Rank -->
          <span class="text-base w-7 text-center flex-shrink-0 font-bold tabular-nums"
                :class="i === 0 ? 'text-amber-500' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-700' : 'text-gray-300 text-sm font-normal'">
            {{ i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1 }}
          </span>
          <span class="flex-1 text-sm font-medium truncate"
                :class="i === 0 ? 'text-amber-900' : 'text-gray-800'">
            {{ u.user_name || u.user_id }}
          </span>
          <span class="text-sm font-semibold tabular-nums"
                :class="i === 0 ? 'text-amber-600' : 'text-gray-600'">
            {{ u.total.toLocaleString() }}
            <span class="text-xs font-normal text-gray-400">則</span>
          </span>
        </div>
      </div>

      <!-- 訊息類型圓餅圖 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">訊息類型分佈</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
        <Pie :data="pieChartData" :options="pieOptions" style="max-height:200px" />
      </div>

      <!-- 夜貓子排行 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">夜貓子排行
        <span class="text-gray-400 font-normal normal-case">0–4 點</span>
      </h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y overflow-hidden">
        <div v-for="(u, i) in data.night_owls" :key="u.user_id"
             class="flex items-center px-4 py-3 gap-3">
          <span class="text-gray-300 text-sm w-5 tabular-nums font-medium">{{ i + 1 }}</span>
          <span class="flex-1 text-sm text-gray-800 truncate">{{ u.user_name || u.user_id }}</span>
          <span class="text-sm font-semibold tabular-nums text-indigo-600">
            {{ u.night_count }}
            <span class="text-xs font-normal text-gray-400">則</span>
          </span>
        </div>
        <div v-if="!data.night_owls.length" class="px-4 py-4 text-sm text-gray-400 text-center">
          無夜貓子資料
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Pie } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { api } from '@/api/client'

ChartJS.register(ArcElement, Tooltip, Legend)

const data = ref<any>(null)
const loading = ref(true)
const error = ref('')

const TYPE_COLORS: Record<string, string> = {
  text: '#60a5fa', sticker: '#f472b6', image: '#34d399',
  video: '#fb923c', audio: '#a78bfa', file: '#94a3b8',
}

const pieChartData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const dist = data.value.type_distribution
  return {
    labels: dist.map((d: any) => d.type),
    datasets: [{
      data: dist.map((d: any) => d.count),
      backgroundColor: dist.map((d: any) => TYPE_COLORS[d.type] || '#94a3b8'),
      borderWidth: 0,
    }],
  }
})

const pieOptions = {
  responsive: true,
  plugins: { legend: { position: 'bottom' as const, labels: { font: { size: 12 } } } },
}

onMounted(async () => {
  try { data.value = await api.leaderboard() }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
})
</script>
