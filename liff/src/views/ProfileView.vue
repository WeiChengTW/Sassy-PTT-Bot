<template>
  <div class="space-y-6">
    <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
      <span>👤 個人成就檔案</span>
    </h1>

    <div v-if="loading" class="space-y-4">
      <!-- Skeleton header -->
      <div class="flex items-center gap-3.5 bg-white rounded-2xl p-4 border border-slate-100">
        <div class="skeleton w-14 h-14 rounded-full shrink-0" />
        <div class="flex-1 space-y-2">
          <div class="skeleton h-5 w-28 rounded-full" />
          <div class="skeleton h-3 w-40 rounded-full" />
        </div>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div v-for="i in 4" :key="i" class="bg-white rounded-2xl p-4 border border-slate-100">
          <div class="skeleton h-8 w-14 rounded mb-2" />
          <div class="skeleton h-3 w-16 rounded-full" />
        </div>
      </div>
    </div>

    <EmptyState
      v-else-if="error"
      icon="⚠️"
      title="無法載入個人資料"
      :description="error"
    />

    <div v-else-if="data" class="space-y-6">
      <!-- User profile header card -->
      <BaseCard class="p-4 flex items-center gap-3.5 card-rise">
        <div class="relative w-14 h-14 rounded-full overflow-hidden bg-brand-100 shrink-0 flex items-center justify-center border-2 border-white shadow-sm">
          <img v-if="userAvatar" :src="userAvatar" :alt="userName" class="w-full h-full object-cover" />
          <span v-else class="text-2xl">👤</span>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <h2 class="text-lg font-bold text-slate-900 truncate">{{ userName }}</h2>
            <span class="text-[10px] px-2 py-0.5 rounded-full font-bold bg-brand-50 text-brand-700 border border-brand-200/60 shrink-0">
              群組成員
            </span>
          </div>
          <p class="text-xs text-slate-400 mt-0.5 truncate">
            首度發言：{{ firstSeenText }}
          </p>
        </div>
      </BaseCard>

      <!-- Summary cards -->
      <div class="grid grid-cols-2 gap-3 stagger">
        <StatCard
          class="card-rise"
          label="總發言量"
          :value="data.summary.total"
          icon="💬"
          variant="brand"
        />
        <StatCard
          class="card-rise"
          label="活躍天數"
          :value="data.summary.active_days"
          icon="🔥"
          variant="success"
        />
        <StatCard
          class="card-rise"
          label="平均日發言"
          :value="data.summary.avg_per_day"
          icon="📊"
          variant="purple"
        />
        <StatCard
          class="card-rise"
          label="平均情緒指數"
          :value="data.avg_sentiment != null ? (data.avg_sentiment >= 0 ? '+' : '') + data.avg_sentiment.toFixed(2) : 'N/A'"
          icon="😊"
          variant="accent"
        />
      </div>

      <!-- 聊天人格 -->
      <template v-if="data.personality && data.personality.length">
        <div>
          <SectionHeader title="聊天人格特質" icon="✨" />
          <div class="rounded-2xl p-4 bg-gradient-to-br from-brand-50/90 via-purple-50/40 to-accent-50/60 border border-brand-200/70 shadow-card space-y-3 card-rise">
            <div v-for="(p, i) in data.personality" :key="i" class="flex items-center gap-3 bg-white/70 backdrop-blur-xs p-2.5 rounded-xl border border-white/80">
              <span class="text-2xl">{{ TAG_EMOJI[p.tag] || '✨' }}</span>
              <div class="min-w-0">
                <p class="text-sm font-bold text-slate-800">{{ p.tag }}</p>
                <p class="text-xs text-slate-500">{{ p.reason }}</p>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- 訊息類型分佈 -->
      <div>
        <SectionHeader title="訊息類型偏好" icon="🧩" />
        <BaseCard class="p-4 card-rise">
          <Bar :data="typeBarData" :options="barOptions" style="max-height:180px" />
        </BaseCard>
      </div>

      <!-- 活躍時段分佈 -->
      <div>
        <SectionHeader title="時段活躍度" icon="🕒" />
        <BaseCard class="p-4 card-rise">
          <div class="grid grid-cols-4 gap-2 text-center text-sm">
            <div v-for="slot in slotList" :key="slot.key"
                 class="bg-slate-50 rounded-xl p-2.5 border border-slate-100">
              <p class="text-lg">{{ slot.emoji }}</p>
              <p class="font-bold font-mono tabular-nums text-slate-800 mt-0.5">{{ data.time_slots[slot.key] }}</p>
              <p class="text-[11px] text-slate-400 mt-0.5">{{ slot.label }}</p>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- 24h 分佈 -->
      <div>
        <SectionHeader title="24 小時作息分佈" icon="⏰" />
        <BaseCard class="p-4 card-rise">
          <Bar :data="hourlyBarData" :options="hourlyOptions" style="max-height:160px" />
        </BaseCard>
      </div>

      <!-- 常聊話題 -->
      <div>
        <SectionHeader title="常聊話題詞彙" icon="💬" />
        <BaseCard class="overflow-hidden card-rise">
          <div class="divide-y divide-slate-100">
            <div v-for="t in data.top_topics" :key="t.topic"
                 class="flex items-center px-4 py-3">
              <span class="flex-1 text-sm font-semibold text-slate-700"># {{ t.topic }}</span>
              <span class="text-sm font-bold font-mono tabular-nums text-slate-400">{{ t.count }} 次</span>
            </div>
            <div v-if="!data.top_topics.length" class="px-4 py-6 text-sm text-slate-400 text-center">
              尚無常聊話題資料
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- 里程碑 -->
      <template v-if="milestones && milestones.total">
        <div>
          <SectionHeader title="個人里程碑榮譽" icon="🏆" />
          <div class="grid grid-cols-2 gap-3 stagger">
            <BaseCard v-if="milestones.nth" class="p-4 card-rise">
              <p class="text-xs text-slate-400 font-semibold">第 {{ milestones.nth.n.toLocaleString() }} 則達成</p>
              <p class="text-base font-bold text-slate-800 mt-1">🎉 {{ fmtMs(milestones.nth.timestamp) }}</p>
            </BaseCard>
            <BaseCard v-if="milestones.busiest_day" class="p-4 card-rise">
              <p class="text-xs text-slate-400 font-semibold">單日最高紀錄</p>
              <p class="text-base font-bold text-slate-800 mt-1">{{ milestones.busiest_day.count }} 則</p>
              <p class="text-[11px] text-slate-400 mt-0.5">{{ milestones.busiest_day.date }}</p>
            </BaseCard>
            <BaseCard v-if="milestones.longest_streak" class="p-4 card-rise">
              <p class="text-xs text-slate-400 font-semibold">最長連續發言</p>
              <p class="text-base font-bold text-slate-800 mt-1">🔥 {{ milestones.longest_streak.days }} 天</p>
              <p class="text-[10px] text-slate-400 mt-0.5 truncate">{{ milestones.longest_streak.start }} ~ {{ milestones.longest_streak.end }}</p>
            </BaseCard>
            <BaseCard class="p-4 card-rise">
              <p class="text-xs text-slate-400 font-semibold">累積發言總量</p>
              <p class="text-base font-bold text-slate-800 mt-1">{{ milestones.total.toLocaleString() }} 則</p>
            </BaseCard>
          </div>
        </div>
      </template>

      <!-- 成長曲線 -->
      <template v-if="hasGrowth">
        <div>
          <SectionHeader title="發言成長軌跡" icon="📈" subtitle="累積訊息總數" />
          <BaseCard class="p-4 card-rise">
            <Line :data="growthLineData" :options="lineOptions" style="max-height:180px" />
          </BaseCard>
        </div>
      </template>

      <!-- 情緒曲線 -->
      <template v-if="hasSentiment">
        <div>
          <SectionHeader title="每日情緒起伏" icon="😊" subtitle="正負向平均" />
          <BaseCard class="p-4 card-rise">
            <Line :data="sentimentLineData" :options="lineOptions" style="max-height:180px" />
          </BaseCard>
        </div>
      </template>

      <!-- 社交圈 -->
      <template v-if="socialCircle.length">
        <div>
          <SectionHeader title="最常互動的夥伴" icon="🤝" />
          <BaseCard class="overflow-hidden card-rise">
            <div class="divide-y divide-slate-100">
              <div v-for="p in socialCircle" :key="p.user_id" class="px-4 py-3.5">
                <div class="flex items-center">
                  <span class="flex-1 text-sm font-bold text-slate-800 truncate">{{ p.name }}</span>
                  <span class="text-xs font-bold font-mono text-brand-600 bg-brand-50 px-2 py-0.5 rounded-full">
                    {{ p.count }} 次互動
                  </span>
                </div>
                <div v-if="p.shared_topics.length" class="flex flex-wrap gap-1 mt-2">
                  <span v-for="t in p.shared_topics" :key="t"
                        class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                    #{{ t }}
                  </span>
                </div>
              </div>
            </div>
          </BaseCard>
        </div>
      </template>

      <!-- 徽章收藏牆 -->
      <template v-if="badges.length">
        <div>
          <SectionHeader title="勳章收藏牆" icon="🎖️" :subtitle="`已獲得 ${badges.length} 枚`" />
          <BaseCard class="p-4 card-rise">
            <div class="grid grid-cols-4 gap-3">
              <div v-for="b in badges" :key="b.badge_id || b.trip_id"
                   class="flex flex-col items-center text-center group cursor-pointer">
                <div class="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl border transition-transform duration-150 group-hover:scale-105"
                     :class="rarityOf(b.badge_rarity).card">
                  {{ b.badge_emoji }}
                </div>
                <p class="text-[10px] font-bold text-slate-700 mt-1.5 line-clamp-2 leading-tight">
                  {{ (b.badge_name || b.title || b.location || '').split('・')[0] }}
                </p>
              </div>
            </div>
          </BaseCard>
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
import { useRefreshOnAnalysis } from '@/composables/useRefreshOnAnalysis'
import { rarityOf } from '@/constants/rarity'
import BaseCard from '@/components/BaseCard.vue'
import StatCard from '@/components/StatCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import SectionHeader from '@/components/SectionHeader.vue'

ChartJS.register(
  CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, Filler, Tooltip, Legend,
)

const auth = useAuthStore()
const data = ref<any>(null)
const loading = ref(true)
const error = ref('')

const slotList = [
  { key: 'night',   emoji: '🌙', label: '深夜 0-4' },
  { key: 'morning', emoji: '🌅', label: '早晨 5-8' },
  { key: 'daytime', emoji: '☀️', label: '白天 9-17' },
  { key: 'evening', emoji: '🌆', label: '晚上 18-23' },
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
      borderRadius: 6,
    }],
  }
})

const barOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { display: false } },
    y: { grid: { color: 'rgba(226,232,240,0.6)' } },
  },
}

const hourlyBarData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const h = data.value.hourly_distribution
  return {
    labels: h.map((d: any) => `${d.hour}h`),
    datasets: [{
      data: h.map((d: any) => d.count),
      backgroundColor: h.map((d: any) => {
        const hr = d.hour
        if (hr < 5)  return '#818cf8'
        if (hr < 9)  return '#fb923c'
        if (hr < 18) return '#60a5fa'
        return '#f472b6'
      }),
      borderRadius: 4,
    }],
  }
})

const hourlyOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { display: false } },
    y: { grid: { color: 'rgba(226,232,240,0.6)' } },
  },
}

const lineOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  elements: { point: { radius: 0 } },
  scales: {
    x: { ticks: { maxTicksLimit: 6 }, grid: { display: false } },
    y: { grid: { color: 'rgba(226,232,240,0.6)' } },
  },
}

const growthLineData = computed(() => {
  const g = data.value?.growth || []
  return {
    labels: g.map((d: any) => d.date),
    datasets: [{
      data: g.map((d: any) => d.cumulative),
      borderColor: '#6366f1',
      backgroundColor: 'rgba(99,102,241,0.12)',
      fill: true,
      tension: 0.3,
      borderWidth: 2.5,
    }],
  }
})

const sentimentLineData = computed(() => {
  const s = data.value?.sentiment_series || []
  return {
    labels: s.map((d: any) => d.date),
    datasets: [{
      data: s.map((d: any) => d.avg_sentiment),
      borderColor: '#f59e0b',
      backgroundColor: 'rgba(245,158,11,0.12)',
      fill: true,
      tension: 0.3,
      borderWidth: 2.5,
    }],
  }
})

function fmtMs(ts: number | null | undefined): string {
  if (!ts) return ''
  const d = new Date(ts)
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

const milestones = computed(() => data.value?.milestones || null)
const socialCircle = computed(() => data.value?.social_circle || [])
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

async function loadProfile() {
  try { data.value = await api.profile(auth.userId) }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
}

onMounted(async () => {
  await loadProfile()
  loading.value = false
})
useRefreshOnAnalysis(loadProfile)
</script>
