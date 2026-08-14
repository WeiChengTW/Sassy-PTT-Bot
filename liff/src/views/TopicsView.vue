<template>
  <div>
    <h1 class="text-xl font-bold mb-4 text-gray-900">話題分析</h1>
    <div v-if="loading">
      <div class="skeleton h-4 w-28 rounded-full mb-3" />
      <div class="skeleton rounded-2xl mb-6" style="height:220px" />
      <div class="skeleton h-4 w-28 rounded-full mb-3" />
      <div class="skeleton rounded-2xl mb-6" style="height:180px" />
      <div class="skeleton h-4 w-20 rounded-full mb-3" />
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm divide-y">
        <div v-for="i in 5" :key="i" class="flex items-center px-4 py-3 gap-3">
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
      <!-- 熱門話題 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">熱門話題 Top 10</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
        <Bar :data="topicBarData" :options="barOptions" style="max-height:220px" />
      </div>

      <!-- 情緒曲線 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">群組情緒曲線</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
        <Line :data="sentimentLineData" :options="lineOptions" style="max-height:180px" />
      </div>

      <!-- 話題列表 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">話題總覽</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y overflow-hidden">
        <div v-for="t in data.top_topics" :key="t.topic"
             class="flex items-center px-4 py-2">
          <span class="flex-1 text-sm">{{ t.topic }}</span>
          <span class="text-sm font-semibold tabular-nums text-gray-500">{{ t.count }} 次</span>
        </div>
        <div v-if="!data.top_topics.length" class="px-4 py-3 text-sm text-gray-400">
          尚無已分析話題
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
  BarElement, PointElement, LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js'
import { api } from '@/api/client'

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const data = ref<any>(null)
const loading = ref(true)
const error = ref('')

const topicBarData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const top10 = data.value.top_topics.slice(0, 10)
  return {
    labels: top10.map((t: any) => t.topic),
    datasets: [{ label: '提及次數', data: top10.map((t: any) => t.count), backgroundColor: '#60a5fa' }],
  }
})

const barOptions = {
  responsive: true,
  indexAxis: 'y' as const,
  plugins: { legend: { display: false } },
}

const sentimentLineData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const rows = data.value.daily_sentiment.slice(-30)
  return {
    labels: rows.map((r: any) => r.date),
    datasets: [{
      label: '情緒值',
      data: rows.map((r: any) => r.avg_sentiment),
      borderColor: '#34d399',
      backgroundColor: 'rgba(52,211,153,0.1)',
      fill: true,
      tension: 0.4,
    }],
  }
})

const lineOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: { y: { min: -1, max: 1 } },
}

onMounted(async () => {
  try { data.value = await api.topics() }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
})
</script>
