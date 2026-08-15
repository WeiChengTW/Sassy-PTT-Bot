<template>
  <div>
    <h1 class="text-xl font-bold mb-4 text-gray-900">個人檔案</h1>
    <div v-if="loading">
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div v-for="i in 4" :key="i" class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
          <div class="skeleton h-8 w-14 rounded mb-2" />
          <div class="skeleton h-3 w-16 rounded-full" />
        </div>
      </div>
      <div class="skeleton h-4 w-24 rounded-full mb-3" />
      <div class="skeleton rounded-2xl mb-6" style="height:180px" />
      <div class="skeleton h-4 w-24 rounded-full mb-3" />
      <div class="bg-white rounded-2xl border border-gray-100 p-4 mb-6 shadow-sm">
        <div class="grid grid-cols-4 gap-2">
          <div v-for="i in 4" :key="i" class="skeleton rounded-xl h-20" />
        </div>
      </div>
    </div>
    <div v-else-if="error" class="flex flex-col items-center py-16 text-center gap-2">
      <p class="text-3xl">⚠️</p>
      <p class="text-sm font-medium text-gray-700">無法載入資料</p>
      <p class="text-xs text-gray-400">{{ error }}</p>
    </div>
    <div v-else-if="data">
      <!-- Summary cards -->
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="bg-blue-50 border border-blue-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-blue-700">{{ data.summary.total.toLocaleString() }}</p>
          <p class="text-xs text-blue-500 mt-0.5">總訊息數</p>
        </div>
        <div class="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-emerald-700">{{ data.summary.active_days }}</p>
          <p class="text-xs text-emerald-500 mt-0.5">活躍天數</p>
        </div>
        <div class="bg-violet-50 border border-violet-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-violet-700">{{ data.summary.avg_per_day }}</p>
          <p class="text-xs text-violet-500 mt-0.5">平均每日</p>
        </div>
        <div class="bg-amber-50 border border-amber-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-amber-700">
            {{ data.avg_sentiment != null ? (data.avg_sentiment >= 0 ? '+' : '') + data.avg_sentiment.toFixed(2) : 'N/A' }}
          </p>
          <p class="text-xs text-amber-500 mt-0.5">平均情緒</p>
        </div>
      </div>

      <!-- 聊天人格 -->
      <template v-if="data.personality && data.personality.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">你的聊天人格</h2>
        <div class="bg-gradient-to-br from-indigo-50 to-violet-50 border border-indigo-100 rounded-2xl p-4 mb-6 space-y-2.5">
          <div v-for="(p, i) in data.personality" :key="i" class="flex items-center gap-3">
            <span class="text-2xl">{{ TAG_EMOJI[p.tag] || '✨' }}</span>
            <div class="min-w-0">
              <p class="text-sm font-bold text-indigo-800">{{ p.tag }}</p>
              <p class="text-xs text-indigo-500">{{ p.reason }}</p>
            </div>
          </div>
        </div>
      </template>

      <!-- 訊息類型 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">訊息類型</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
        <Bar :data="typeBarData" :options="barOptions" style="max-height:180px" />
      </div>

      <!-- 時段分佈 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">活躍時段</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
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
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">24 小時分佈</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
        <Bar :data="hourlyBarData" :options="hourlyOptions" style="max-height:160px" />
      </div>

      <!-- 話題 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">常聊話題</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y overflow-hidden">
        <div v-for="t in data.top_topics" :key="t.topic"
             class="flex items-center px-4 py-3">
          <span class="flex-1 text-sm text-gray-800">{{ t.topic }}</span>
          <span class="text-sm font-semibold tabular-nums text-gray-500">{{ t.count }} 次</span>
        </div>
        <div v-if="!data.top_topics.length" class="px-4 py-4 text-sm text-gray-400 text-center">
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
const error = ref('')

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

const TAG_EMOJI: Record<string, string> = {
  貼圖狂魔: '🎭', 攝影大師: '📸', 文字控: '⌨️', 夜貓子: '🌙',
  日行性: '☀️', 正能量大使: '😊', 毒舌代表: '🌶️', 均衡型: '⚖️', 潛水中: '🤿',
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
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
})
</script>
