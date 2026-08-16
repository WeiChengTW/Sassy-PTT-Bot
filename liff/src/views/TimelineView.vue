<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
          <span>🕰️ 回憶時光軸</span>
        </h1>
        <p class="text-xs text-slate-400 mt-0.5 font-medium">
          共 {{ trips.length }} 段群組記憶
          <span v-if="trips.length"> · {{ oldestYear }}–{{ newestYear }}</span>
        </p>
      </div>
    </div>

    <!-- 稀有度圖例 -->
    <div v-if="trips.length" class="flex flex-wrap gap-2">
      <span
        v-for="r in legend"
        :key="r.key"
        class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold shadow-2xs"
        :class="r.pill"
      >
        <span>{{ r.emoji }}</span>
        <span>{{ r.zh }}</span>
        <span class="opacity-80 font-mono text-[10px] font-bold">({{ counts[r.key] || 0 }})</span>
      </span>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="skeleton h-16 rounded-2xl" />
    </div>

    <EmptyState
      v-else-if="!trips.length"
      icon="🕰️"
      title="尚無回憶紀錄"
      description="發起新的群組旅行與活動，解鎖第一段精彩回憶！"
    />

    <div v-else class="space-y-8">
      <section v-for="group in grouped" :key="group.year">
        <h2 class="text-xs font-bold font-mono text-brand-700 uppercase tracking-widest mb-3 sticky top-10 bg-slate-50/90 backdrop-blur-md py-1 z-10 px-1">
          📌 {{ group.year }} 年
        </h2>
        <div class="relative pl-6">
          <!-- 縱向時間線 -->
          <div class="absolute left-[7px] top-2 bottom-2 w-0.5 bg-slate-200/80" />
          
          <div v-for="t in group.items" :key="t.id" class="relative mb-3.5 card-rise">
            <!-- 稀有度圓點 -->
            <span
              class="absolute -left-[23px] top-4 w-4 h-4 rounded-full ring-4 ring-white shrink-0 shadow-sm"
              :class="rarityOf(t.rarity).dot"
            />
            
            <div
              class="rounded-2xl border p-3.5 flex items-center gap-3 transition-all duration-200"
              :class="rarityOf(t.rarity).card"
            >
              <div class="flex-1 min-w-0">
                <p class="font-bold text-sm truncate text-slate-800">
                  {{ t.title }}
                </p>
                <p class="text-xs mt-0.5 font-medium" :class="rarityOf(t.rarity).date">
                  🗓️ {{ formatRange(t) }}
                </p>
              </div>
              <span
                class="shrink-0 inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold"
                :class="rarityOf(t.rarity).pill"
              >
                {{ rarityOf(t.rarity).emoji }} {{ rarityOf(t.rarity).zh }}
              </span>
              <button
                @click.stop="onQuickShare(t.id)"
                :disabled="sharingId === t.id"
                class="shrink-0 p-2 rounded-xl text-slate-400 hover:text-brand-600 hover:bg-white/80 active:scale-95 disabled:opacity-40 transition-all btn-press"
                aria-label="分享這段回憶"
              >
                <svg v-if="sharingId !== t.id" class="w-4 h-4" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M4 12v7a1 1 0 001 1h14a1 1 0 001-1v-7" />
                  <path d="M16 6l-4-4-4 4" />
                  <path d="M12 2v14" />
                </svg>
                <svg v-else class="w-4 h-4 animate-spin text-brand-600" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" stroke-opacity="0.25" />
                  <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client'
import { RARITY, rarityOf } from '@/constants/rarity'
import { buildTripFlex } from '@/utils/flexTripCard'
import { shareFlexMessage } from '@/utils/liffShare'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/EmptyState.vue'

const toast = useToast()
const trips = ref<any[]>([])
const loading = ref(true)
const sharingId = ref<string | null>(null)

async function onQuickShare(id: string) {
  if (sharingId.value) return
  sharingId.value = id
  try {
    const detail = await api.tripDetail(id)
    const res = await shareFlexMessage(buildTripFlex(detail))
    if (res.success) toast.success('已分享回顧小卡 🎉')
    else if (res.mode === 'picker') toast.error('已取消分享')
  } catch (e: any) {
    toast.error(e?.message || '分享失敗，請稍後再試')
  } finally {
    sharingId.value = null
  }
}

const legend = Object.values(RARITY)

const sorted = computed(() =>
  [...trips.value].sort((a, b) => (b.start_date || 0) - (a.start_date || 0)),
)

const counts = computed<Record<string, number>>(() => {
  const c: Record<string, number> = {}
  for (const t of trips.value) {
    const key = rarityOf(t.rarity).key
    c[key] = (c[key] || 0) + 1
  }
  return c
})

const grouped = computed(() => {
  const map = new Map<number, any[]>()
  for (const t of sorted.value) {
    const y = new Date((t.start_date || 0) * 1000).getFullYear()
    if (!map.has(y)) map.set(y, [])
    map.get(y)!.push(t)
  }
  return [...map.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([year, items]) => ({ year, items }))
})

const oldestYear = computed(() =>
  trips.value.length ? Math.min(...trips.value.map((t) => new Date((t.start_date || 0) * 1000).getFullYear())) : '',
)
const newestYear = computed(() =>
  trips.value.length ? Math.max(...trips.value.map((t) => new Date((t.start_date || 0) * 1000).getFullYear())) : '',
)

function fmt(ts: number): string {
  const d = new Date(ts * 1000)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function formatRange(t: any): string {
  const start = fmt(t.start_date)
  if (!t.end_date || t.end_date === t.start_date) return start
  return `${start}–${fmt(t.end_date)}`
}

onMounted(async () => {
  try { trips.value = await api.trips() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
