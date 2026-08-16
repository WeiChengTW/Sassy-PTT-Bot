<template>
  <div class="space-y-6">
    <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
      <span>⚡ 群組動態脈搏</span>
    </h1>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-4">
      <div class="skeleton h-32 rounded-2xl" />
      <div class="skeleton h-36 rounded-2xl" />
    </div>

    <EmptyState
      v-else-if="error"
      icon="⚠️"
      title="無法載入動態資料"
      :description="error"
    />

    <div v-else-if="data" class="space-y-6">
      <!-- 回應速度 -->
      <div>
        <SectionHeader title="群組回應速度" icon="⚡" />
        <BaseCard class="p-5 card-rise">
          <div class="flex items-baseline gap-2 mb-1">
            <span class="text-3xl font-black font-mono tabular-nums text-brand-600">
              {{ data.response_speed.avg_minutes !== null ? data.response_speed.avg_minutes : '—' }}
            </span>
            <span class="text-xs font-semibold text-slate-400">分鐘 · 平均回覆時效</span>
          </div>
          <p v-if="!data.response_speed.fastest_responders.length" class="text-xs text-slate-400 mt-2">
            目前還沒有足夠的回覆資料
          </p>
          <div v-else class="mt-4 pt-3 border-t border-slate-100 divide-y divide-slate-100">
            <p class="text-xs font-bold text-slate-400 mb-2">⚡ 閃電神回手</p>
            <div
              v-for="(u, i) in data.response_speed.fastest_responders"
              :key="u.user_id"
              class="flex items-center py-2.5 gap-3"
            >
              <span class="text-slate-300 text-xs w-5 font-bold font-mono tabular-nums">{{ i + 1 }}</span>
              <span class="flex-1 text-xs font-bold text-slate-800 truncate">{{ u.name }}</span>
              <span class="text-xs font-bold font-mono tabular-nums text-brand-600 bg-brand-50 px-2 py-0.5 rounded-full">
                {{ u.avg_minutes }} 分鐘
              </span>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- 訊息爆發 -->
      <div>
        <SectionHeader title="熱門話題爆發時段" icon="🔥" :subtitle="`平均每小時 ${data.avg_hourly} 則`" />
        <BaseCard class="overflow-hidden card-rise">
          <div v-if="!data.bursts.length" class="px-4 py-8 text-center text-xs text-slate-400">
            尚無明顯爆發時段
          </div>
          <div v-else class="divide-y divide-slate-100">
            <div
              v-for="(b, i) in data.bursts"
              :key="b.hour"
              class="flex items-center px-4 py-3 gap-3"
            >
              <span class="text-slate-300 text-xs w-5 font-bold font-mono tabular-nums">{{ i + 1 }}</span>
              <span class="flex-1 text-xs font-semibold text-slate-700 font-mono">{{ b.hour }}:00</span>
              <span class="text-accent-500 text-xs">{{ '⚡'.repeat(Math.min(3, Math.round(b.ratio))) }}</span>
              <span class="text-xs font-bold font-mono tabular-nums text-slate-700">{{ b.count }} 則</span>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- 潛水員 -->
      <div>
        <SectionHeader title="群組潛水員偵測" icon="🤿" />
        <BaseCard class="overflow-hidden card-rise">
          <div v-if="!data.lurkers.length" class="px-4 py-8 text-center text-xs font-bold text-success-600">
            🎉 沒有人潛水，全員活躍熱絡中！
          </div>
          <div v-else class="divide-y divide-slate-100">
            <div
              v-for="u in data.lurkers"
              :key="u.user_id"
              class="flex items-center px-4 py-3 gap-3"
            >
              <span class="text-base">🤿</span>
              <span class="flex-1 text-xs font-semibold text-slate-800 truncate">{{ u.name }}</span>
              <span class="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-mono">
                {{ u.days_inactive !== null ? `${u.days_inactive} 天未發言` : '從未發言' }}
              </span>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import { useRefreshOnAnalysis } from '@/composables/useRefreshOnAnalysis'
import BaseCard from '@/components/BaseCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import SectionHeader from '@/components/SectionHeader.vue'

const data = ref<any>(null)
const loading = ref(true)
const error = ref('')

async function loadPulse() {
  try { data.value = await api.pulse() }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
}

onMounted(async () => {
  await loadPulse()
  loading.value = false
})
useRefreshOnAnalysis(loadPulse)
</script>
