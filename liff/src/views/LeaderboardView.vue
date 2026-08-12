<template>
  <div>
    <h1 class="text-xl font-bold mb-4">🏆 排行榜</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="data">
      <!-- 訊息量排行 -->
      <h2 class="font-semibold mb-2 mt-4">📣 活躍度排行</h2>
      <div class="bg-white rounded-xl shadow divide-y mb-6">
        <div v-for="(u, i) in data.rankings" :key="u.user_id"
             class="flex items-center px-4 py-2 gap-3">
          <span class="text-gray-400 text-sm w-6">
            {{ i === 0 ? '👑' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1 }}
          </span>
          <span class="flex-1 text-sm">{{ u.user_name || u.user_id }}</span>
          <span class="text-sm font-medium">{{ u.total }} 則</span>
        </div>
      </div>

      <!-- 訊息類型圓餅圖 -->
      <h2 class="font-semibold mb-2">📊 訊息類型分佈</h2>
      <div class="bg-white rounded-xl shadow p-4 mb-6">
        <Pie :data="pieChartData" :options="pieOptions" style="max-height:200px" />
      </div>

      <!-- 夜貓子排行 -->
      <h2 class="font-semibold mb-2">🌙 夜貓子排行 (0–4 點)</h2>
      <div class="bg-white rounded-xl shadow divide-y">
        <div v-for="(u, i) in data.night_owls" :key="u.user_id"
             class="flex items-center px-4 py-2 gap-3">
          <span class="text-gray-400 text-sm w-5">{{ i + 1 }}</span>
          <span class="flex-1 text-sm">{{ u.user_name || u.user_id }}</span>
          <span class="text-sm font-medium">{{ u.night_count }} 則</span>
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
    }],
  }
})

const pieOptions = { responsive: true, plugins: { legend: { position: 'bottom' as const } } }

onMounted(async () => {
  try { data.value = await api.leaderboard() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
