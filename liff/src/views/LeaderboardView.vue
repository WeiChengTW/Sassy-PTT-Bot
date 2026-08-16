<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
        <span>🏆 榮譽排行榜</span>
      </h1>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-6">
      <div class="skeleton h-4 w-32 rounded-full" />
      <div class="bg-white rounded-2xl p-4 border border-slate-100 divide-y divide-slate-100">
        <div v-for="i in 5" :key="i" class="flex items-center py-3 gap-3">
          <div class="skeleton w-6 h-4 rounded" />
          <div class="skeleton flex-1 h-4 rounded-full" />
          <div class="skeleton w-12 h-4 rounded" />
        </div>
      </div>
    </div>

    <EmptyState
      v-else-if="error"
      icon="⚠️"
      title="無法載入資料"
      :description="error"
    />

    <div v-else-if="data" class="space-y-6">
      <!-- 徽章成就排行 -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <SectionHeader title="徽章成就榜" icon="🏅" class="!mt-0 !mb-0" />
          <SegmentedControl
            v-model="badgeSortMode"
            :options="[
              { label: '加權積分', value: 'weighted' },
              { label: '總枚數', value: 'count' }
            ]"
          />
        </div>
        <p class="text-[11px] text-slate-400 mb-3" v-if="badgeSortMode === 'weighted'">
          計分規則：傳說 2.0 · 史詩 1.5 · 極稀有 1.0 · 稀有 0.8 · 普通 0.5
        </p>
        
        <BaseCard class="overflow-hidden card-rise">
          <div class="divide-y divide-slate-100">
            <div
              v-for="(u, i) in sortedBadgeRankings"
              :key="u.user_id"
              class="flex items-center px-4 py-3.5 gap-3 transition-colors hover:bg-slate-50/80"
              :class="i === 0 ? 'bg-accent-50/40' : i === 1 ? 'bg-slate-50/60' : ''"
            >
              <!-- Medal / Rank -->
              <span
                class="text-sm w-6 text-center font-bold tabular-nums shrink-0"
                :class="i === 0 ? 'text-accent-600' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-700' : 'text-slate-300 font-normal'"
              >
                {{ i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1 }}
              </span>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-bold truncate" :class="i === 0 ? 'text-amber-950' : 'text-slate-800'">
                  {{ u.user_name || u.user_id }}
                </p>
                <!-- 稀有度分佈 pills -->
                <div class="flex items-center gap-1.5 mt-1 text-[10px] flex-wrap">
                  <span v-if="u.legendary_count" class="px-1.5 py-0.2 rounded bg-rose-50 text-rose-600 font-bold border border-rose-100">
                    傳說 {{ u.legendary_count }}
                  </span>
                  <span v-if="u.epic_count" class="px-1.5 py-0.2 rounded bg-purple-50 text-purple-600 font-bold border border-purple-100">
                    史詩 {{ u.epic_count }}
                  </span>
                  <span v-if="u.super_rare_count" class="px-1.5 py-0.2 rounded bg-amber-50 text-amber-700 font-bold border border-amber-100">
                    極稀有 {{ u.super_rare_count }}
                  </span>
                  <span v-if="u.rare_count" class="px-1.5 py-0.2 rounded bg-sky-50 text-sky-700 font-medium border border-sky-100">
                    稀有 {{ u.rare_count }}
                  </span>
                  <span v-if="u.common_count" class="px-1.5 py-0.2 rounded bg-slate-50 text-slate-600 font-medium border border-slate-200">
                    普通 {{ u.common_count }}
                  </span>
                </div>
              </div>
              <div class="text-right shrink-0">
                <template v-if="badgeSortMode === 'weighted'">
                  <span
                    class="text-base font-black font-mono tabular-nums"
                    :class="i === 0 ? 'text-accent-600' : 'text-brand-600'"
                  >
                    {{ u.score }}
                  </span>
                  <span class="text-[10px] font-medium text-slate-400 block -mt-1">分 ({{ u.badge_count }}枚)</span>
                </template>
                <template v-else>
                  <span
                    class="text-base font-black font-mono tabular-nums"
                    :class="i === 0 ? 'text-accent-600' : 'text-slate-800'"
                  >
                    {{ u.badge_count }}
                  </span>
                  <span class="text-xs font-normal text-slate-400 block -mt-1">枚徽章</span>
                </template>
              </div>
            </div>
            <div v-if="!sortedBadgeRankings.length" class="px-4 py-8 text-sm text-slate-400 text-center">
              尚無徽章數據
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- 發言活躍排行 -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <SectionHeader title="發言活躍排行" icon="💬" class="!mt-0 !mb-0" />
          <SegmentedControl
            v-model="activeMessageFilter"
            :options="[
              { label: '全部', value: 'all' },
              { label: '文字', value: 'text' },
              { label: '貼圖', value: 'sticker' },
              { label: '圖片', value: 'image' }
            ]"
          />
        </div>

        <BaseCard class="overflow-hidden card-rise">
          <div class="divide-y divide-slate-100">
            <div
              v-for="(u, i) in sortedMessageRankings"
              :key="u.user_id"
              class="flex items-center px-4 py-3.5 gap-3 transition-colors hover:bg-slate-50/80"
              :class="i === 0 ? 'bg-accent-50/40' : i === 1 ? 'bg-slate-50/60' : ''"
            >
              <!-- Medal / Rank -->
              <span
                class="text-sm w-6 text-center font-bold tabular-nums shrink-0"
                :class="i === 0 ? 'text-accent-600' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-700' : 'text-slate-300 font-normal'"
              >
                {{ i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1 }}
              </span>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-bold truncate" :class="i === 0 ? 'text-amber-950' : 'text-slate-800'">
                  {{ u.user_name || u.user_id }}
                </p>
                <!-- 訊息類型分佈 pills -->
                <div class="flex items-center gap-1.5 mt-1 text-[10px] flex-wrap">
                  <span v-if="u.text_count" class="px-1.5 py-0.2 rounded bg-blue-50 text-blue-600 font-medium border border-blue-100">
                    💬 {{ u.text_count }}
                  </span>
                  <span v-if="u.sticker_count" class="px-1.5 py-0.2 rounded bg-pink-50 text-pink-600 font-medium border border-pink-100">
                    🎭 {{ u.sticker_count }}
                  </span>
                  <span v-if="u.image_count" class="px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-600 font-medium border border-emerald-100">
                    📸 {{ u.image_count }}
                  </span>
                  <span v-if="u.video_count" class="px-1.5 py-0.2 rounded bg-orange-50 text-orange-600 font-medium border border-orange-100">
                    🎬 {{ u.video_count }}
                  </span>
                </div>
              </div>
              <div class="text-right shrink-0">
                <span
                  class="text-base font-black font-mono tabular-nums"
                  :class="i === 0 ? 'text-accent-600' : 'text-slate-800'"
                >
                  {{ (displayCountOf(u)).toLocaleString() }}
                </span>
                <span class="text-xs font-normal text-slate-400 block -mt-1">則{{ filterUnitText }}</span>
              </div>
            </div>
            <div v-if="!sortedMessageRankings.length" class="px-4 py-8 text-sm text-slate-400 text-center">
              尚無發言數據
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- 訊息類型圓餅圖 -->
      <div>
        <SectionHeader title="訊息型態佔比" icon="🥧" />
        <BaseCard class="p-4 card-rise">
          <Pie :data="pieChartData" :options="pieOptions" style="max-height:200px" />
        </BaseCard>
      </div>

      <!-- 夜貓子排行 -->
      <div>
        <SectionHeader title="夜貓子排行榜" icon="🦉" subtitle="0–4 點深夜發言" />
        <BaseCard class="overflow-hidden card-rise">
          <div class="divide-y divide-slate-100">
            <div
              v-for="(u, i) in data.night_owls"
              :key="u.user_id"
              class="flex items-center px-4 py-3.5 gap-3"
            >
              <span class="text-slate-300 text-sm w-5 tabular-nums font-medium">{{ i + 1 }}</span>
              <span class="flex-1 text-sm font-semibold text-slate-800 truncate">{{ u.user_name || u.user_id }}</span>
              <span class="text-sm font-bold font-mono tabular-nums text-purple-600">
                {{ u.night_count }}
                <span class="text-xs font-normal text-slate-400">則</span>
              </span>
            </div>
            <div v-if="!data.night_owls.length" class="px-4 py-8 text-sm text-slate-400 text-center">
              深夜無人發言，大家作息都很健康 🌙
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- 更多排行榜（資料驅動） -->
      <div v-if="boards.length">
        <SectionHeader title="更多自訂排行榜" icon="🎯" />
        <div class="flex flex-wrap gap-2 mb-4">
          <button
            v-for="b in boards"
            :key="b.id"
            @click="selectedId = b.id"
            class="px-3.5 py-1.5 rounded-full text-xs font-bold border transition-all duration-150 btn-press whitespace-nowrap select-none"
            :class="selectedId === b.id
              ? 'bg-brand-600 text-white border-brand-600 shadow-sm ring-2 ring-brand-200'
              : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'"
          >
            {{ b.emoji }} {{ b.title }}
          </button>
        </div>
        <BoardCard v-if="selectedBoard" :board="selectedBoard" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Pie } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { api, type Board } from '@/api/client'
import { useRefreshOnAnalysis } from '@/composables/useRefreshOnAnalysis'
import BoardCard from '@/components/BoardCard.vue'
import BaseCard from '@/components/BaseCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import SectionHeader from '@/components/SectionHeader.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'

ChartJS.register(ArcElement, Tooltip, Legend)

const data = ref<any>(null)
const loading = ref(true)
const error = ref('')
const badgeSortMode = ref<'weighted' | 'count'>('weighted')
const activeMessageFilter = ref<'all' | 'text' | 'sticker' | 'image'>('all')
const boards = ref<Board[]>([])
const selectedId = ref('')
const selectedBoard = computed(() => boards.value.find(b => b.id === selectedId.value) || null)

const sortedBadgeRankings = computed(() => {
  const list = [...(data.value?.badge_rankings || [])]
  if (badgeSortMode.value === 'weighted') {
    return list.sort((a, b) => {
      if ((b.score ?? 0) !== (a.score ?? 0)) return (b.score ?? 0) - (a.score ?? 0)
      if ((b.legendary_count ?? 0) !== (a.legendary_count ?? 0)) return (b.legendary_count ?? 0) - (a.legendary_count ?? 0)
      return (b.badge_count ?? 0) - (a.badge_count ?? 0)
    })
  } else {
    return list.sort((a, b) => {
      if ((b.badge_count ?? 0) !== (a.badge_count ?? 0)) return (b.badge_count ?? 0) - (a.badge_count ?? 0)
      if ((b.legendary_count ?? 0) !== (a.legendary_count ?? 0)) return (b.legendary_count ?? 0) - (a.legendary_count ?? 0)
      return (b.score ?? 0) - (a.score ?? 0)
    })
  }
})

function displayCountOf(u: any): number {
  if (activeMessageFilter.value === 'text') return u.text_count ?? 0
  if (activeMessageFilter.value === 'sticker') return u.sticker_count ?? 0
  if (activeMessageFilter.value === 'image') return u.image_count ?? 0
  return u.total ?? 0
}

const filterUnitText = computed(() => {
  if (activeMessageFilter.value === 'text') return '文字'
  if (activeMessageFilter.value === 'sticker') return '貼圖'
  if (activeMessageFilter.value === 'image') return '圖片'
  return ''
})

const sortedMessageRankings = computed(() => {
  const list = [...(data.value?.rankings || [])]
  return list.sort((a, b) => displayCountOf(b) - displayCountOf(a))
})

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
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: {
        font: { size: 12, family: 'Inter, Noto Sans TC' },
        padding: 12,
      },
    },
  },
}

async function loadLeaderboards() {
  try {
    const [lead, more] = await Promise.all([api.leaderboard(), api.leaderboards()])
    data.value = lead
    boards.value = more.boards || []
    if (boards.value.length && !selectedId.value) selectedId.value = boards.value[0].id
  }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
}

onMounted(async () => {
  await loadLeaderboards()
  loading.value = false
})
useRefreshOnAnalysis(loadLeaderboards)
</script>
