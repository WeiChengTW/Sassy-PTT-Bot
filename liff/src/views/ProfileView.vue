<template>
  <div>
    <h1 class="text-xl font-bold mb-4 text-gray-900">個人檔案</h1>
    <div v-if="loading">
      <!-- User info header skeleton -->
      <div class="flex items-center gap-3.5 bg-white rounded-2xl p-4 shadow-sm border border-gray-100 mb-4">
        <div class="skeleton w-14 h-14 rounded-full flex-shrink-0" />
        <div class="flex-1 space-y-2">
          <div class="skeleton h-5 w-28 rounded-full" />
          <div class="skeleton h-3 w-40 rounded-full" />
        </div>
      </div>
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
      <!-- User profile header -->
      <div class="flex items-center gap-3.5 bg-white rounded-2xl p-4 shadow-sm border border-gray-100 mb-4">
        <div class="relative w-14 h-14 rounded-full overflow-hidden bg-blue-100 flex-shrink-0 flex items-center justify-center border border-gray-200">
          <img v-if="userAvatar" :src="userAvatar" :alt="userName" class="w-full h-full object-cover" />
          <span v-else class="text-2xl">👤</span>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <h2 class="text-lg font-bold text-gray-900 truncate">{{ userName }}</h2>
            <span class="text-[10px] px-2 py-0.5 rounded-full font-medium bg-blue-50 text-blue-600 border border-blue-100 shrink-0">
              個人數據
            </span>
          </div>
          <p class="text-xs text-gray-400 mt-0.5 truncate">
            首見：{{ firstSeenText }}
          </p>
        </div>
      </div>

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

      <!-- 里程碑 -->
      <template v-if="milestones && milestones.total">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2 mt-6">🏆 個人里程碑</h2>
        <div class="grid grid-cols-2 gap-3 mb-6">
          <div v-if="milestones.nth" class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <p class="text-xs text-gray-400">第 {{ milestones.nth.n.toLocaleString() }} 則達成</p>
            <p class="text-lg font-bold text-gray-800 mt-0.5">🎉 {{ fmtMs(milestones.nth.timestamp) }}</p>
          </div>
          <div v-if="milestones.busiest_day" class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <p class="text-xs text-gray-400">單日最高</p>
            <p class="text-lg font-bold text-gray-800 mt-0.5">{{ milestones.busiest_day.count }} 則</p>
            <p class="text-xs text-gray-400">{{ milestones.busiest_day.date }}</p>
          </div>
          <div v-if="milestones.longest_streak" class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <p class="text-xs text-gray-400">最長連續發言</p>
            <p class="text-lg font-bold text-gray-800 mt-0.5">🔥 {{ milestones.longest_streak.days }} 天</p>
            <p class="text-xs text-gray-400">{{ milestones.longest_streak.start }} ~ {{ milestones.longest_streak.end }}</p>
          </div>
          <div class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <p class="text-xs text-gray-400">累積訊息</p>
            <p class="text-lg font-bold text-gray-800 mt-0.5">{{ milestones.total.toLocaleString() }} 則</p>
          </div>
        </div>
      </template>

      <!-- 成長曲線 -->
      <template v-if="hasGrowth">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">📈 成長曲線（累積訊息）</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
          <Line :data="growthLineData" :options="lineOptions" style="max-height:180px" />
        </div>
      </template>

      <!-- 情緒曲線 -->
      <template v-if="hasSentiment">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">😊 情緒曲線（每日平均）</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
          <Line :data="sentimentLineData" :options="lineOptions" style="max-height:180px" />
        </div>
      </template>

      <!-- 社交圈 -->
      <template v-if="socialCircle.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">🤝 你最常互動的人</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y overflow-hidden mb-6">
          <div v-for="p in socialCircle" :key="p.user_id" class="px-4 py-3">
            <div class="flex items-center">
              <span class="flex-1 text-sm font-medium text-gray-800 truncate">{{ p.name }}</span>
              <span class="text-sm font-semibold tabular-nums text-gray-500">{{ p.count }} 次互動</span>
            </div>
            <div v-if="p.shared_topics.length" class="flex flex-wrap gap-1 mt-1.5">
              <span v-for="t in p.shared_topics" :key="t"
                    class="text-[11px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600">#{{ t }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 旅行足跡 -->
      <template v-if="footprints.trips.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">
          🗺️ 旅行足跡（參與 {{ footprints.participated }} · 發起 {{ footprints.initiated }}）
        </h2>
        <div class="space-y-2 mb-6">
          <router-link v-for="t in footprints.trips" :key="t.id" :to="`/trips/${t.id}`"
                       class="flex items-center gap-3 rounded-2xl border p-3"
                       :class="rarityOf(t.rarity).card">
            <span class="text-2xl shrink-0">{{ t.badge_emoji }}</span>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold truncate" :class="rarityOf(t.rarity).name">
                {{ t.title }}
                <span v-if="t.is_creator" class="text-[10px] align-middle ml-1 px-1.5 py-0.5 rounded-full bg-white/70 text-gray-600">發起</span>
              </p>
              <p class="text-xs" :class="rarityOf(t.rarity).date">{{ t.location }} · {{ fmtSec(t.start_date) }}</p>
            </div>
          </router-link>
        </div>
      </template>

      <!-- 徽章收藏牆 -->
      <template v-if="badges.length">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">🎖️ 徽章收藏牆（已獲得 {{ badges.length }} 枚）</h2>
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
          <div class="grid grid-cols-4 gap-3">
            <div v-for="b in badges" :key="b.badge_id || b.trip_id"
                 class="flex flex-col items-center text-center">
              <div class="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl border"
                   :class="rarityOf(b.badge_rarity).card">
                {{ b.badge_emoji }}
              </div>
              <p class="text-[10px] text-gray-500 mt-1 line-clamp-2 leading-tight">{{ b.location || b.badge_name }}</p>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Bar, Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, Filler, Tooltip, Legend,
} from 'chart.js'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { rarityOf } from '@/constants/rarity'

ChartJS.register(
  CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, Filler, Tooltip, Legend,
)

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

// ── 成長 / 情緒曲線 ──
const lineOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  elements: { point: { radius: 0 } },
  scales: { x: { ticks: { maxTicksLimit: 6 } } },
}

const growthLineData = computed(() => {
  const g = data.value?.growth || []
  return {
    labels: g.map((d: any) => d.date),
    datasets: [{
      data: g.map((d: any) => d.cumulative),
      borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.12)',
      fill: true, tension: 0.3, borderWidth: 2,
    }],
  }
})

const sentimentLineData = computed(() => {
  const s = data.value?.sentiment_series || []
  return {
    labels: s.map((d: any) => d.date),
    datasets: [{
      data: s.map((d: any) => d.avg_sentiment),
      borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.12)',
      fill: true, tension: 0.3, borderWidth: 2,
    }],
  }
})

// ── 格式化 ──
function fmtMs(ts: number | null | undefined): string {
  if (!ts) return ''
  const d = new Date(ts)
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}
function fmtSec(ts: number | null | undefined): string {
  return ts ? fmtMs(ts * 1000) : ''
}

const milestones = computed(() => data.value?.milestones || null)
const socialCircle = computed(() => data.value?.social_circle || [])
const footprints = computed(() => data.value?.footprints || { trips: [], participated: 0, initiated: 0 })
const badges = computed(() => data.value?.badges || [])
const hasGrowth = computed(() => (data.value?.growth || []).length > 1)
const hasSentiment = computed(() => (data.value?.sentiment_series || []).length > 1)

const userName = computed(() => {
  return auth.displayName || data.value?.display_name || '群組成員'
})

const userAvatar = computed(() => {
  return auth.pictureUrl || ''
})

const firstSeenText = computed(() => {
  const ts = data.value?.summary?.first_seen
  if (!ts) return '近期'
  const d = new Date(ts)
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
})

onMounted(async () => {
  try { data.value = await api.profile(auth.userId) }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
})
</script>
