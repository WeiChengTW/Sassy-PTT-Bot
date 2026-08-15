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
      <!-- 徽章成就排行 -->
      <div class="flex items-center justify-between mb-2">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide">🏅 徽章成就排行</h2>
        <!-- 切換按鈕: 加權積分 vs 總枚數 -->
        <div class="flex rounded-lg bg-gray-100 p-0.5 border border-gray-200">
          <button type="button" @click="badgeSortMode = 'weighted'"
                  class="px-2.5 py-0.5 text-xs rounded-md font-medium transition-all"
                  :class="badgeSortMode === 'weighted' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-800'">
            加權積分
          </button>
          <button type="button" @click="badgeSortMode = 'count'"
                  class="px-2.5 py-0.5 text-xs rounded-md font-medium transition-all"
                  :class="badgeSortMode === 'count' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-800'">
            總枚數
          </button>
        </div>
      </div>
      <p class="text-[11px] text-gray-400 mb-2" v-if="badgeSortMode === 'weighted'">
        計分規則：傳說 2.0 · 史詩 1.5 · 極稀有 1.0 · 稀有 0.8 · 普通 0.5 (楊教授提供)
      </p>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y mb-6 overflow-hidden">
        <div v-for="(u, i) in sortedBadgeRankings" :key="u.user_id"
             class="flex items-center px-4 py-3 gap-3"
             :class="i === 0 ? 'bg-amber-50/60' : i === 1 ? 'bg-slate-50/60' : ''">
          <!-- Medal / Rank -->
          <span class="text-base w-7 text-center flex-shrink-0 font-bold tabular-nums"
                :class="i === 0 ? 'text-amber-500' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-700' : 'text-gray-300 text-sm font-normal'">
            {{ i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1 }}
          </span>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-bold truncate" :class="i === 0 ? 'text-amber-950' : 'text-gray-800'">
              {{ u.user_name || u.user_id }}
            </p>
            <!-- 稀有度分佈 pills -->
            <div class="flex items-center gap-1.5 mt-1 text-[10px] flex-wrap">
              <span v-if="u.legendary_count" class="px-1.5 py-0.2 rounded bg-rose-50 text-rose-600 font-semibold border border-rose-100">
                傳說 {{ u.legendary_count }}
              </span>
              <span v-if="u.epic_count" class="px-1.5 py-0.2 rounded bg-purple-50 text-purple-600 font-semibold border border-purple-100">
                史詩 {{ u.epic_count }}
              </span>
              <span v-if="u.super_rare_count" class="px-1.5 py-0.2 rounded bg-amber-50 text-amber-700 font-semibold border border-amber-100">
                極稀有 {{ u.super_rare_count }}
              </span>
              <span v-if="u.rare_count" class="px-1.5 py-0.2 rounded bg-blue-50 text-blue-600 font-medium border border-blue-100">
                稀有 {{ u.rare_count }}
              </span>
              <span v-if="u.common_count" class="px-1.5 py-0.2 rounded bg-gray-50 text-gray-600 font-medium border border-gray-100">
                普通 {{ u.common_count }}
              </span>
            </div>
          </div>
          <div class="text-right shrink-0">
            <template v-if="badgeSortMode === 'weighted'">
              <span class="text-base font-black tabular-nums"
                    :class="i === 0 ? 'text-amber-600' : 'text-blue-600'">
                {{ u.score }}
              </span>
              <span class="text-[10px] font-normal text-gray-400 block -mt-1">分 ({{ u.badge_count }}枚)</span>
            </template>
            <template v-else>
              <span class="text-base font-black tabular-nums"
                    :class="i === 0 ? 'text-amber-600' : 'text-gray-800'">
                {{ u.badge_count }}
              </span>
              <span class="text-xs font-normal text-gray-400 block -mt-1">枚徽章</span>
            </template>
          </div>
        </div>
        <div v-if="!sortedBadgeRankings.length" class="px-4 py-4 text-sm text-gray-400 text-center">
          尚無徽章數據
        </div>
      </div>

      <!-- 活躍度排行 -->
      <div class="flex items-center justify-between mb-2">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide">💬 發言活躍排行</h2>
        <!-- 切換按鈕: 全部 vs 文字 vs 貼圖 vs 圖片 -->
        <div class="flex rounded-lg bg-gray-100 p-0.5 border border-gray-200 text-xs">
          <button type="button" @click="activeMessageFilter = 'all'"
                  class="px-2 py-0.5 rounded-md font-medium transition-all"
                  :class="activeMessageFilter === 'all' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-800'">
            全部
          </button>
          <button type="button" @click="activeMessageFilter = 'text'"
                  class="px-2 py-0.5 rounded-md font-medium transition-all"
                  :class="activeMessageFilter === 'text' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-800'">
            文字
          </button>
          <button type="button" @click="activeMessageFilter = 'sticker'"
                  class="px-2 py-0.5 rounded-md font-medium transition-all"
                  :class="activeMessageFilter === 'sticker' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-800'">
            貼圖
          </button>
          <button type="button" @click="activeMessageFilter = 'image'"
                  class="px-2 py-0.5 rounded-md font-medium transition-all"
                  :class="activeMessageFilter === 'image' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-800'">
            圖片
          </button>
        </div>
      </div>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y mb-6 overflow-hidden">
        <div v-for="(u, i) in sortedMessageRankings" :key="u.user_id"
             class="flex items-center px-4 py-3 gap-3"
             :class="i === 0 ? 'bg-amber-50/60' : i === 1 ? 'bg-slate-50/60' : ''">
          <!-- Medal / Rank -->
          <span class="text-base w-7 text-center flex-shrink-0 font-bold tabular-nums"
                :class="i === 0 ? 'text-amber-500' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-700' : 'text-gray-300 text-sm font-normal'">
            {{ i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1 }}
          </span>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-bold truncate" :class="i === 0 ? 'text-amber-950' : 'text-gray-800'">
              {{ u.user_name || u.user_id }}
            </p>
            <!-- 訊息類型分佈 pills -->
            <div class="flex items-center gap-1.5 mt-1 text-[10px] flex-wrap">
              <span v-if="u.text_count" class="px-1.5 py-0.2 rounded bg-blue-50 text-blue-600 font-medium border border-blue-100">
                💬 文字 {{ u.text_count }}
              </span>
              <span v-if="u.sticker_count" class="px-1.5 py-0.2 rounded bg-pink-50 text-pink-600 font-medium border border-pink-100">
                🎭 貼圖 {{ u.sticker_count }}
              </span>
              <span v-if="u.image_count" class="px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-600 font-medium border border-emerald-100">
                📸 圖片 {{ u.image_count }}
              </span>
              <span v-if="u.video_count" class="px-1.5 py-0.2 rounded bg-orange-50 text-orange-600 font-medium border border-orange-100">
                🎬 影片 {{ u.video_count }}
              </span>
            </div>
          </div>
          <div class="text-right shrink-0">
            <span class="text-base font-black tabular-nums"
                  :class="i === 0 ? 'text-amber-600' : 'text-gray-800'">
              {{ (displayCountOf(u)).toLocaleString() }}
            </span>
            <span class="text-xs font-normal text-gray-400 block -mt-1">則{{ filterUnitText }}</span>
          </div>
        </div>
        <div v-if="!sortedMessageRankings.length" class="px-4 py-4 text-sm text-gray-400 text-center">
          尚無發言數據
        </div>
      </div>

      <!-- 訊息類型圓餅圖 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">訊息類型分佈</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
        <Pie :data="pieChartData" :options="pieOptions" style="max-height:200px" />
      </div>

      <!-- 夜貓子排行 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">🦉 夜貓子排行
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

      <!-- 更多排行榜（資料驅動） -->
      <div v-if="boards.length" class="mt-8">
        <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-3">🎯 更多排行榜</h2>
        <!-- 排行榜選單：emoji chip 自動換行（全部一次可見） -->
        <div class="flex flex-wrap gap-2 mb-4">
          <button v-for="b in boards" :key="b.id" @click="selectedId = b.id"
                  class="px-3 py-1.5 rounded-full text-sm border transition-colors whitespace-nowrap"
                  :class="selectedId === b.id
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-gray-600 border-gray-200'">
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
import BoardCard from '@/components/BoardCard.vue'

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
  plugins: { legend: { position: 'bottom' as const, labels: { font: { size: 12 } } } },
}

onMounted(async () => {
  try {
    const [lead, more] = await Promise.all([api.leaderboard(), api.leaderboards()])
    data.value = lead
    boards.value = more.boards || []
    if (boards.value.length) selectedId.value = boards.value[0].id
  }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
})
</script>
