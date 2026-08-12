<template>
  <div>
    <h1 class="text-xl font-bold mb-4">👤 個人檔案</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="data">
      <!-- Summary cards -->
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.total }}</p>
          <p class="text-xs text-gray-500">總訊息數</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.active_days }}</p>
          <p class="text-xs text-gray-500">活躍天數</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.avg_per_day }}</p>
          <p class="text-xs text-gray-500">平均每日</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">
            {{ data.avg_sentiment != null ? (data.avg_sentiment >= 0 ? '+' : '') + data.avg_sentiment.toFixed(2) : 'N/A' }}
          </p>
          <p class="text-xs text-gray-500">平均情緒</p>
        </div>
      </div>

      <!-- 訊息類型 -->
      <h2 class="font-semibold mb-2">📊 訊息類型</h2>
      <div class="bg-white rounded-xl shadow p-4 mb-6">
        <Bar :data="typeBarData" :options="barOptions" style="max-height:180px" />
      </div>

      <!-- 時段分佈 -->
      <h2 class="font-semibold mb-2">🕐 活躍時段</h2>
      <div class="bg-white rounded-xl shadow p-4 mb-6">
        <div class="grid grid-cols-4 gap-2 text-center text-sm">
          <div v-for="slot in slotList" :key="slot.key"
               class="bg-gray-50 rounded-lg p-2">
            <p class="text-lg">{{ slot.emoji }}</p>
            <p class="font-semibold">{{ data.time_slots[slot.key] }}</p>
            <p class="text-xs text-gray-500">{{ slot.label }}</p>
          </div>
        </div>
      </div>

      <!-- 24h 分佈 -->
      <h2 class="font-semibold mb-2">📈 24 小時分佈</h2>
      <div class="bg-white rounded-xl shadow p-4 mb-6">
        <Bar :data="hourlyBarData" :options="hourlyOptions" style="max-height:160px" />
      </div>

      <!-- 話題 -->
      <h2 class="font-semibold mb-2">🏷️ 常聊話題</h2>
      <div class="bg-white rounded-xl shadow divide-y">
        <div v-for="t in data.top_topics" :key="t.topic"
             class="flex items-center px-4 py-2">
          <span class="flex-1 text-sm">{{ t.topic }}</span>
          <span class="text-sm text-gray-500">{{ t.count }} 次</span>
        </div>
        <div v-if="!data.top_topics.length" class="px-4 py-3 text-sm text-gray-400">
          尚無話題資料
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const auth = useAuthStore()
const data = ref<any>(null)
const loading = ref(true)

const slotList = [
  { key: 'night',   emoji: '🌙', label: '深夜 (0-4)' },
  { key: 'morning', emoji: '🌅', label: '早晨 (5-8)' },
  { key: 'daytime', emoji: '☀️', label: '白天 (9-17)' },
  { key: 'evening', emoji: '🌆', label: '晚上 (18-23)' },
]

const TYPE_COLORS: Record<string, string> = {
  text: '#60a5fa', sticker: '#f472b6', image: '#34d399',
  video: '#fb923c', audio: '#a78bfa', file: '#94a3b8',
}

const typeBarData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const breakdown = data.value.type_breakdown
  return {
    labels: breakdown.map((d: any) => d.type),
    datasets: [{
      label: '訊息數',
      data: breakdown.map((d: any) => d.count),
      backgroundColor: breakdown.map((d: any) => TYPE_COLORS[d.type] || '#94a3b8'),
    }],
  }
})

const barOptions = { responsive: true, plugins: { legend: { display: false } } }

const hourlyBarData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const h = data.value.hourly_distribution
  return {
    labels: h.map((d: any) => `${d.hour}時`),
    datasets: [{
      data: h.map((d: any) => d.count),
      backgroundColor: h.map((d: any) => {
        const hr = d.hour
        if (hr < 5)  return '#818cf8'  // 深夜紫
        if (hr < 9)  return '#fb923c'  // 早晨橙
        if (hr < 18) return '#60a5fa'  // 白天藍
        return '#f472b6'               // 夜晚粉
      }),
    }],
  }
})

const hourlyOptions = { responsive: true, plugins: { legend: { display: false } } }

onMounted(async () => {
  try { data.value = await api.profile(auth.userId) }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
