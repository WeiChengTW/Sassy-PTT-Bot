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
      <!-- 熱門關鍵字文字雲 -->
      <template v-if="data.top_keywords && data.top_keywords.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">熱門關鍵字</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-2 mb-6">
          <WordCloud :words="cloudWords" />
        </div>
      </template>

      <!-- 熱門話題 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">熱門話題 Top 10</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
        <Bar :data="topicBarData" :options="barOptions" style="max-height:220px" />
      </div>

      <!-- 情緒分佈 -->
      <template v-if="data.sentiment_distribution && data.sentiment_distribution.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">情緒分佈</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
          <Doughnut :data="sentimentDistData" :options="doughnutOptions" style="max-height:220px" />
        </div>
      </template>

      <!-- 話題情緒 -->
      <template v-if="data.topic_sentiment && data.topic_sentiment.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">各話題平均情緒</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y overflow-hidden mb-6">
          <div v-for="t in data.topic_sentiment" :key="t.topic" class="flex items-center px-4 py-2.5 gap-3">
            <span class="w-14 text-sm text-gray-700">{{ t.topic }}</span>
            <div class="flex-1 h-2 rounded-full bg-gray-100 relative overflow-hidden">
              <div class="absolute top-0 bottom-0 rounded-full"
                   :style="sentimentBarStyle(t.avg_sentiment)" />
            </div>
            <span class="text-xs tabular-nums w-12 text-right"
                  :class="t.avg_sentiment >= 0 ? 'text-emerald-600' : 'text-rose-500'">
              {{ t.avg_sentiment > 0 ? '+' : '' }}{{ t.avg_sentiment.toFixed(2) }}
            </span>
          </div>
        </div>
      </template>

      <!-- 情緒曲線 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">群組情緒曲線</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
        <Line :data="sentimentLineData" :options="lineOptions" style="max-height:180px" />
      </div>

      <!-- 熱門地點 -->
      <template v-if="data.hot_locations && data.hot_locations.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">熱門地點</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6 flex flex-wrap gap-2">
          <span v-for="l in data.hot_locations" :key="l.location"
                class="inline-flex items-center gap-1 rounded-lg bg-amber-50 border border-amber-100 px-2.5 py-1 text-xs text-amber-700">
            📍 {{ l.location }}
            <span class="opacity-60 tabular-nums">{{ l.count }}</span>
          </span>
        </div>
      </template>

      <!-- 精選語錄：情緒最鮮明的原話 -->
      <template v-if="data.highlight_quotes && data.highlight_quotes.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">精選語錄</h2>
        <p class="text-xs text-gray-400 mb-2">情緒最鮮明的發言（最正面 / 最負面）</p>
        <div class="space-y-2 mb-6">
          <div v-for="(q, i) in data.highlight_quotes" :key="i"
               class="bg-white rounded-2xl shadow-sm border-l-4 px-4 py-3"
               :class="q.tone === 'positive' ? 'border-emerald-400' : 'border-rose-400'">
            <div class="flex items-center gap-1.5 mb-1">
              <span class="text-xs font-semibold px-1.5 py-0.5 rounded"
                    :class="q.tone === 'positive' ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-500'">
                {{ q.tone === 'positive' ? '🔥 最正面' : '💢 最負面' }}
              </span>
              <span class="text-xs tabular-nums"
                    :class="q.tone === 'positive' ? 'text-emerald-500' : 'text-rose-400'">
                {{ q.sentiment > 0 ? '+' : '' }}{{ q.sentiment.toFixed(2) }}
              </span>
            </div>
            <p class="text-sm text-gray-800 leading-snug">「{{ q.content }}」</p>
            <p class="text-xs text-gray-400 mt-1">— {{ q.user_name }}</p>
          </div>
        </div>
      </template>

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
import { Bar, Line, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, ArcElement,
  BarElement, PointElement, LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js'
import { api } from '@/api/client'
import WordCloud from '@/components/WordCloud.vue'

ChartJS.register(CategoryScale, LinearScale, ArcElement, BarElement, PointElement, LineElement, Title, Tooltip, Legend, Filler)

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

const SENT_COLORS: Record<string, string> = {
  非常正面: '#10b981', 正面: '#6ee7b7', 中性: '#cbd5e1',
  負面: '#fca5a5', 非常負面: '#ef4444',
}

const sentimentDistData = computed(() => {
  if (!data.value?.sentiment_distribution) return { labels: [], datasets: [] }
  const rows = data.value.sentiment_distribution
  return {
    labels: rows.map((r: any) => `${r.category} ${r.percentage}%`),
    datasets: [{
      data: rows.map((r: any) => r.count),
      backgroundColor: rows.map((r: any) => SENT_COLORS[r.category] || '#94a3b8'),
    }],
  }
})

const doughnutOptions = {
  responsive: true,
  plugins: { legend: { position: 'bottom' as const, labels: { boxWidth: 12, font: { size: 11 } } } },
}

const cloudWords = computed(() =>
  (data.value?.top_keywords || []).map((k: any) => ({ text: k.keyword, count: k.count })),
)

function sentimentBarStyle(v: number) {
  // -1..1 映射到中線兩側
  const pct = Math.min(Math.abs(v), 1) * 50
  if (v >= 0) {
    return { left: '50%', width: `${pct}%`, background: '#34d399' }
  }
  return { right: '50%', width: `${pct}%`, background: '#f87171' }
}

onMounted(async () => {
  try { data.value = await api.topics() }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
})
</script>
