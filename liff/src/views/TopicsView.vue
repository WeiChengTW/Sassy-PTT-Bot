<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
          <span>🧠 群組話題與情緒</span>
        </h1>
        <p v-if="data?.last_analyzed_at" class="text-[11px] text-slate-400 font-mono mt-0.5">
          最後分析：{{ formatAnalyzedTime(data.last_analyzed_at) }}
        </p>
      </div>
      <!-- 管理員觸發重新分析按鈕 -->
      <button
        v-if="auth.role === 'admin'"
        @click="triggerReanalyze"
        :disabled="analyzing"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-brand-50 text-brand-600 border border-brand-200 hover:bg-brand-100 disabled:opacity-50 transition-all btn-press shadow-xs"
      >
        <span :class="analyzing ? 'animate-spin' : ''">🔄</span>
        <span>{{ analyzing ? 'LLM 分析中...' : '重新分析' }}</span>
      </button>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-4">
      <div class="skeleton h-48 rounded-2xl" />
      <div class="skeleton h-40 rounded-2xl" />
    </div>

    <EmptyState
      v-else-if="error"
      icon="⚠️"
      title="無法載入話題資料"
      :description="error"
    />

    <div v-else-if="data" class="space-y-6">
      <!-- 熱門關鍵字文字雲 -->
      <template v-if="data.top_keywords && data.top_keywords.length">
        <div>
          <SectionHeader title="熱門話題關鍵字雲" icon="☁️" />
          <BaseCard class="p-3 card-rise overflow-hidden">
            <WordCloud :words="cloudWords" />
          </BaseCard>
        </div>
      </template>

      <!-- 熱門話題 -->
      <div>
        <SectionHeader title="熱門話題 Top 10" icon="📊" />
        <BaseCard class="p-4 card-rise">
          <Bar :data="topicBarData" :options="barOptions" style="max-height:220px" />
        </BaseCard>
      </div>

      <!-- 情緒分佈 -->
      <template v-if="data.sentiment_distribution && data.sentiment_distribution.length">
        <div>
          <SectionHeader title="發言情緒佔比" icon="🎭" />
          <BaseCard class="p-4 card-rise">
            <Doughnut :data="sentimentDistData" :options="doughnutOptions" style="max-height:220px" />
          </BaseCard>
        </div>
      </template>

      <!-- 話題情緒 -->
      <template v-if="data.topic_sentiment && data.topic_sentiment.length">
        <div>
          <SectionHeader title="各話題平均情緒指標" icon="🌡️" />
          <BaseCard class="overflow-hidden card-rise">
            <div class="divide-y divide-slate-100">
              <div v-for="t in data.topic_sentiment" :key="t.topic" class="flex items-center px-4 py-3 gap-3">
                <span class="w-20 text-xs font-bold text-slate-700 truncate"># {{ t.topic }}</span>
                <div class="flex-1 h-2 rounded-full bg-slate-100 relative overflow-hidden">
                  <div class="absolute top-0 bottom-0 rounded-full"
                       :style="sentimentBarStyle(t.avg_sentiment)" />
                </div>
                <span class="text-xs font-mono font-bold w-12 text-right tabular-nums"
                      :class="t.avg_sentiment >= 0 ? 'text-success-600' : 'text-danger-500'">
                  {{ t.avg_sentiment > 0 ? '+' : '' }}{{ t.avg_sentiment.toFixed(2) }}
                </span>
              </div>
            </div>
          </BaseCard>
        </div>
      </template>

      <!-- 情緒曲線 -->
      <div>
        <SectionHeader title="情緒波動趨勢曲線" icon="📈" />
        <BaseCard class="p-4 card-rise">
          <Line :data="sentimentLineData" :options="lineOptions" style="max-height:180px" />
        </BaseCard>
      </div>

      <!-- 熱門地點 -->
      <template v-if="data.hot_locations && data.hot_locations.length">
        <div>
          <SectionHeader title="熱門提及地點" icon="📍" />
          <BaseCard class="p-4 flex flex-wrap gap-2 card-rise">
            <span
              v-for="l in data.hot_locations"
              :key="l.location"
              class="inline-flex items-center gap-1.5 rounded-xl bg-accent-50 border border-accent-200/80 px-3 py-1.5 text-xs font-bold text-accent-800"
            >
              <span>📍 {{ l.location }}</span>
              <span class="font-mono text-[11px] opacity-75">({{ l.count }})</span>
            </span>
          </BaseCard>
        </div>
      </template>

      <!-- 精選語錄 -->
      <template v-if="data.highlight_quotes && data.highlight_quotes.length">
        <div>
          <SectionHeader title="情緒精選金句語錄" icon="💬" />
          <div class="space-y-3">
            <div
              v-for="(q, i) in data.highlight_quotes"
              :key="i"
              class="bg-white rounded-2xl shadow-card border-l-4 px-4 py-3.5 card-rise transition-all"
              :class="q.tone === 'positive' ? 'border-success-500' : 'border-danger-500'"
            >
              <div class="flex items-center justify-between mb-1.5">
                <span
                  class="text-[10px] font-bold px-2 py-0.5 rounded-md"
                  :class="q.tone === 'positive' ? 'bg-success-50 text-success-700' : 'bg-danger-50 text-danger-700'"
                >
                  {{ q.tone === 'positive' ? '🔥 滿滿正能量' : '💢 吐槽代表' }}
                </span>
                <span
                  class="text-xs font-mono font-bold tabular-nums"
                  :class="q.tone === 'positive' ? 'text-success-600' : 'text-danger-500'"
                >
                  {{ q.sentiment > 0 ? '+' : '' }}{{ q.sentiment.toFixed(2) }}
                </span>
              </div>
              <p class="text-sm font-semibold text-slate-800 leading-relaxed">「{{ q.content }}」</p>
              <p class="text-xs text-slate-400 mt-1 font-medium text-right">— {{ q.user_name }}</p>
            </div>
          </div>
        </div>
      </template>
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
import { useAuthStore } from '@/stores/auth'
import { useAnalysisStore } from '@/stores/analysis'
import { useToast } from '@/composables/useToast'
import { useRefreshOnAnalysis } from '@/composables/useRefreshOnAnalysis'
import WordCloud from '@/components/WordCloud.vue'
import BaseCard from '@/components/BaseCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import SectionHeader from '@/components/SectionHeader.vue'

ChartJS.register(CategoryScale, LinearScale, ArcElement, BarElement, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const auth = useAuthStore()
const toast = useToast()
const analysis = useAnalysisStore()
const data = ref<any>(null)
const loading = ref(true)
const analyzing = ref(false)
const error = ref('')

async function loadTopics() {
  try { data.value = await api.topics() }
  catch (e: any) { error.value = e?.message || '請求失敗' }
}

function formatAnalyzedTime(ts: number) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function triggerReanalyze() {
  if (analyzing.value) return
  analyzing.value = true
  try {
    const res = await api.adminAnalyzeTopics()
    analysis.bumped(res.updated)
    toast.success(`LLM 分析完成，更新了 ${res.updated} 則訊息 🎉`)
  } catch (e: any) {
    toast.error(e?.message || '分析失敗，請稍後再試')
  } finally {
    analyzing.value = false
  }
}

const topicBarData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const top10 = data.value.top_topics.slice(0, 10)
  return {
    labels: top10.map((t: any) => t.topic),
    datasets: [{
      label: '提及次數',
      data: top10.map((t: any) => t.count),
      backgroundColor: '#6366f1',
      borderRadius: 6,
    }],
  }
})

const barOptions = {
  responsive: true,
  indexAxis: 'y' as const,
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { color: 'rgba(226,232,240,0.6)' } },
    y: { grid: { display: false } },
  },
}

const sentimentLineData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const rows = data.value.daily_sentiment.slice(-30)
  return {
    labels: rows.map((r: any) => r.date),
    datasets: [{
      label: '情緒值',
      data: rows.map((r: any) => r.avg_sentiment),
      borderColor: '#10b981',
      backgroundColor: 'rgba(16,185,129,0.12)',
      fill: true,
      tension: 0.35,
      borderWidth: 2.5,
    }],
  }
})

const lineOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: {
    y: { min: -1, max: 1, grid: { color: 'rgba(226,232,240,0.6)' } },
    x: { grid: { display: false } },
  },
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
      borderWidth: 0,
    }],
  }
})

const doughnutOptions = {
  responsive: true,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: { boxWidth: 12, font: { size: 11, family: 'Inter, Noto Sans TC' }, padding: 12 },
    },
  },
}

const cloudWords = computed(() =>
  (data.value?.top_keywords || []).map((k: any) => ({ text: k.keyword, count: k.count })),
)

function sentimentBarStyle(v: number) {
  const pct = Math.min(Math.abs(v), 1) * 50
  if (v >= 0) {
    return { left: '50%', width: `${pct}%`, background: '#10b981' }
  }
  return { right: '50%', width: `${pct}%`, background: '#f43f5e' }
}

onMounted(async () => {
  await loadTopics()
  loading.value = false
})
useRefreshOnAnalysis(loadTopics)
</script>
