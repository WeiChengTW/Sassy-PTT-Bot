<template>
  <div class="space-y-6">
    <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
      <span>👥 成員互動對比</span>
    </h1>

    <!-- 成員選擇 -->
    <div class="grid grid-cols-2 gap-3">
      <select
        v-model="userA"
        @change="loadCompare"
        class="text-xs bg-white border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 font-semibold focus:outline-none focus:ring-2 focus:ring-brand-400"
      >
        <option value="" disabled>選擇成員 A</option>
        <option v-for="u in members" :key="u.user_id" :value="u.user_id">{{ u.name }}</option>
      </select>
      <select
        v-model="userB"
        @change="loadCompare"
        class="text-xs bg-white border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 font-semibold focus:outline-none focus:ring-2 focus:ring-fuchsia-400"
      >
        <option value="" disabled>選擇成員 B</option>
        <option v-for="u in members" :key="u.user_id" :value="u.user_id">{{ u.name }}</option>
      </select>
    </div>

    <div v-if="membersLoading" class="skeleton rounded-2xl h-48" />
    <EmptyState
      v-else-if="membersError"
      icon="⚠️"
      title="無法載入成員名單"
      :description="membersError"
    />

    <template v-else>
      <EmptyState
        v-if="!userA || !userB"
        icon="⚖️"
        title="請選擇兩位成員"
        description="從上方下拉選單挑選兩位群組好友，立即比較彼此的發言習慣與默契！"
      />
      <EmptyState
        v-else-if="userA === userB"
        icon="🤔"
        title="請選擇兩位不同的成員"
        description="自己跟自己比較相似度一定是 100% 啦！"
      />

      <div v-else-if="loading" class="skeleton rounded-2xl h-48" />
      <EmptyState
        v-else-if="error"
        icon="⚠️"
        title="對比資料載入失敗"
        :description="error"
      />

      <div v-else-if="cmp" class="space-y-4 card-rise">
        <!-- 相似度 -->
        <BaseCard class="p-6 text-center bg-gradient-to-br from-brand-50 via-white to-fuchsia-50 border-brand-100">
          <p class="text-4xl font-black font-mono tabular-nums text-brand-600">
            <CountUp :value="cmp.similarity" :duration="800" :format="(v) => `${v}%`" />
          </p>
          <p class="text-xs font-bold text-slate-600 mt-1">
            默契相似度 · <span class="text-brand-700">{{ similarityLabel }}</span>
          </p>
        </BaseCard>

        <!-- 對比列 -->
        <BaseCard class="overflow-hidden">
          <div class="grid grid-cols-3 px-4 py-3 bg-slate-50 border-b border-slate-100 text-xs font-bold">
            <span class="text-brand-600 truncate">{{ cmp.a.name }}</span>
            <span class="text-center text-slate-300 font-normal">VS</span>
            <span class="text-right text-fuchsia-600 truncate">{{ cmp.b.name }}</span>
          </div>
          <div
            v-for="row in rows"
            :key="row.label"
            class="grid grid-cols-3 px-4 py-3.5 items-center border-t border-slate-100/80 transition-colors hover:bg-slate-50/50"
          >
            <span
              class="text-xs font-bold font-mono tabular-nums"
              :class="row.aWin ? 'text-brand-600 font-black' : 'text-slate-500'"
            >
              {{ row.a }}
            </span>
            <span class="text-center text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              {{ row.label }}
            </span>
            <span
              class="text-xs font-bold font-mono tabular-nums text-right"
              :class="row.bWin ? 'text-fuchsia-600 font-black' : 'text-slate-500'"
            >
              {{ row.b }}
            </span>
          </div>
        </BaseCard>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client'
import { useRefreshOnAnalysis } from '@/composables/useRefreshOnAnalysis'
import BaseCard from '@/components/BaseCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import CountUp from '@/components/CountUp.vue'

const members = ref<{ user_id: string; name: string }[]>([])
const membersLoading = ref(true)
const membersError = ref('')
const userA = ref('')
const userB = ref('')

const cmp = ref<any>(null)
const loading = ref(false)
const error = ref('')

const SLOT_LABELS: Record<string, string> = {
  night: '深夜', morning: '清晨', daytime: '白天', evening: '晚上',
}

const rows = computed(() => {
  if (!cmp.value) return []
  const a = cmp.value.a, b = cmp.value.b
  const num = (label: string, av: number, bv: number, fmt = (x: number) => `${x}`) => ({
    label, a: fmt(av), b: fmt(bv), aWin: av > bv, bWin: bv > av,
  })
  const sentA = a.avg_sentiment, sentB = b.avg_sentiment
  const sentFmt = (x: number | null) => (x === null || x === undefined ? '—' : x.toFixed(2))
  return [
    num('總訊息量', a.total, b.total),
    num('活躍天數', a.active_days, b.active_days),
    num('平均日發言', a.avg_per_day, b.avg_per_day),
    num('文字比例', a.text_ratio, b.text_ratio, (x) => `${x}%`),
    num('貼圖比例', a.sticker_ratio, b.sticker_ratio, (x) => `${x}%`),
    {
      label: '情緒指數', a: sentFmt(sentA), b: sentFmt(sentB),
      aWin: (sentA ?? -2) > (sentB ?? -2), bWin: (sentB ?? -2) > (sentA ?? -2),
    },
    {
      label: '活躍時段',
      a: SLOT_LABELS[a.top_slot] || '—', b: SLOT_LABELS[b.top_slot] || '—',
      aWin: false, bWin: false,
    },
  ]
})

const similarityLabel = computed(() => {
  const s = cmp.value?.similarity ?? 0
  if (s >= 80) return '超級麻吉 🔥'
  if (s >= 60) return '頗有默契 ✨'
  if (s >= 40) return '各有風格 ⚖️'
  return '互補型夥伴 🧩'
})

async function loadCompare() {
  if (!userA.value || !userB.value || userA.value === userB.value) { cmp.value = null; return }
  loading.value = true
  error.value = ''
  try { cmp.value = await api.compare(userA.value, userB.value) }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
}

async function loadMembers() {
  try {
    const dash = await api.dashboard()
    members.value = (dash.top_users || []).map((u: any) => ({
      user_id: u.user_id, name: u.user_name || u.user_id,
    }))
  } catch (e: any) { membersError.value = e?.message || '請求失敗'; console.error(e) }
}

onMounted(async () => {
  await loadMembers()
  membersLoading.value = false
})
useRefreshOnAnalysis(loadMembers)
</script>
