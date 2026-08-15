<template>
  <div>
    <h1 class="text-xl font-bold mb-4 text-gray-900">成員對比</h1>

    <!-- 成員選擇 -->
    <div class="grid grid-cols-2 gap-3 mb-6">
      <select v-model="userA" @change="loadCompare"
              class="text-sm bg-white border border-gray-200 rounded-xl px-3 py-2.5 text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-200">
        <option value="" disabled>選擇成員 A</option>
        <option v-for="u in members" :key="u.user_id" :value="u.user_id">{{ u.name }}</option>
      </select>
      <select v-model="userB" @change="loadCompare"
              class="text-sm bg-white border border-gray-200 rounded-xl px-3 py-2.5 text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-200">
        <option value="" disabled>選擇成員 B</option>
        <option v-for="u in members" :key="u.user_id" :value="u.user_id">{{ u.name }}</option>
      </select>
    </div>

    <div v-if="membersLoading" class="skeleton rounded-2xl" style="height:200px" />
    <div v-else-if="membersError" class="flex flex-col items-center py-16 text-center gap-2">
      <p class="text-3xl">⚠️</p>
      <p class="text-sm font-medium text-gray-700">無法載入成員</p>
      <p class="text-xs text-gray-400">{{ membersError }}</p>
    </div>

    <template v-else>
      <p v-if="!userA || !userB" class="text-center text-sm text-gray-400 py-10">請選擇兩位成員進行比較</p>
      <p v-else-if="userA === userB" class="text-center text-sm text-gray-400 py-10">請選擇兩位不同的成員</p>

      <div v-else-if="loading" class="skeleton rounded-2xl" style="height:200px" />
      <p v-else-if="error" class="text-center text-sm text-rose-500 py-10">{{ error }}</p>

      <div v-else-if="cmp">
        <!-- 相似度 -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4 text-center">
          <p class="text-3xl font-bold tabular-nums text-indigo-600">{{ cmp.similarity }}%</p>
          <p class="text-xs text-gray-400 mt-1">相似度 · {{ similarityLabel }}</p>
        </div>

        <!-- 對比列 -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div class="grid grid-cols-3 px-4 py-2.5 bg-gray-50 text-xs font-medium text-gray-500">
            <span class="text-blue-600 truncate">{{ cmp.a.name }}</span>
            <span class="text-center text-gray-300">vs</span>
            <span class="text-right text-fuchsia-600 truncate">{{ cmp.b.name }}</span>
          </div>
          <div v-for="row in rows" :key="row.label"
               class="grid grid-cols-3 px-4 py-3 items-center border-t border-gray-50">
            <span class="text-sm font-semibold tabular-nums" :class="row.aWin ? 'text-blue-600' : 'text-gray-600'">{{ row.a }}</span>
            <span class="text-center text-[11px] text-gray-400">{{ row.label }}</span>
            <span class="text-sm font-semibold tabular-nums text-right" :class="row.bWin ? 'text-fuchsia-600' : 'text-gray-600'">{{ row.b }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client'

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
    num('訊息量', a.total, b.total),
    num('活躍天數', a.active_days, b.active_days),
    num('日均', a.avg_per_day, b.avg_per_day),
    num('文字比', a.text_ratio, b.text_ratio, (x) => `${x}%`),
    num('貼圖比', a.sticker_ratio, b.sticker_ratio, (x) => `${x}%`),
    {
      label: '情緒分', a: sentFmt(sentA), b: sentFmt(sentB),
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
  if (s >= 80) return '超級麻吉'
  if (s >= 60) return '頗有默契'
  if (s >= 40) return '各有風格'
  return '互補型'
})

async function loadCompare() {
  if (!userA.value || !userB.value || userA.value === userB.value) { cmp.value = null; return }
  loading.value = true
  error.value = ''
  try { cmp.value = await api.compare(userA.value, userB.value) }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
}

onMounted(async () => {
  try {
    const dash = await api.dashboard()
    members.value = (dash.top_users || []).map((u: any) => ({
      user_id: u.user_id, name: u.user_name || u.user_id,
    }))
  } catch (e: any) { membersError.value = e?.message || '請求失敗'; console.error(e) }
  finally { membersLoading.value = false }
})
</script>
