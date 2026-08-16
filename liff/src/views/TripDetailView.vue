<template>
  <div class="space-y-6">
    <button
      @click="$router.back()"
      class="text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors inline-flex items-center gap-1 btn-press px-2.5 py-1.5 rounded-xl bg-white border border-slate-200"
    >
      <span>← 返回列表</span>
    </button>

    <div v-if="loading" class="space-y-4">
      <div class="skeleton h-36 rounded-2xl" />
      <div class="skeleton h-24 rounded-2xl" />
    </div>

    <div v-else-if="detail" class="space-y-6">
      <!-- Hero Card -->
      <div
        class="rounded-2xl border p-5 shadow-card relative overflow-hidden card-rise"
        :class="rarity.card"
      >
        <div class="flex items-start justify-between gap-2">
          <div>
            <h1 class="text-xl font-bold tracking-tight" :class="rarity.name">
              {{ detail.trip.title }}
            </h1>
            <p v-if="detail.trip.location" class="text-xs mt-1 font-medium flex items-center gap-1" :class="rarity.date">
              <span>📍</span>
              <span>{{ detail.trip.location }}</span>
            </p>
            <p v-if="dateRange" class="text-xs mt-0.5 font-medium" :class="rarity.date">
              🗓️ {{ dateRange }}
            </p>
          </div>
          <span
            v-if="detail.trip.rarity"
            class="shrink-0 inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold shadow-2xs"
            :class="rarity.pill"
          >
            {{ rarity.zh }}
          </span>
        </div>

        <div
          v-if="detail.trip.trip_types && detail.trip.trip_types.length"
          class="flex flex-wrap gap-1.5 mt-4"
        >
          <span
            v-for="ty in detail.trip.trip_types"
            :key="ty"
            class="inline-flex items-center gap-1 rounded-xl bg-white/80 backdrop-blur-xs border border-slate-200/60 px-2.5 py-1 text-xs font-medium text-slate-700 shadow-2xs"
          >
            {{ emojiFor(ty) }} {{ labelFor(ty) }}
          </span>
        </div>

        <div class="mt-4 pt-3 border-t border-black/5 flex items-center justify-between text-xs font-semibold" :class="rarity.name">
          <span class="opacity-80">
            狀態：{{ detail.trip.status === 'ended' ? '已圓滿結束' : '進行中 🔥' }}
          </span>
          <span class="font-mono opacity-90">
            💬 {{ detail.stats.message_count }} 則訊息
          </span>
        </div>
      </div>

      <!-- 參與者列表 -->
      <div>
        <SectionHeader title="活動參與者" icon="👥" :subtitle="`共 ${detail.participants.length} 人`" />
        <BaseCard class="overflow-hidden card-rise">
          <div v-if="detail.participants.length" class="divide-y divide-slate-100">
            <div
              v-for="p in detail.participants"
              :key="p.user_id"
              class="px-4 py-3 text-sm flex items-center justify-between"
            >
              <span class="font-semibold text-slate-800">{{ p.user_name || p.user_id }}</span>
              <span class="text-xs px-2 py-0.5 rounded-full bg-slate-100 font-medium text-slate-500">
                {{ p.role || '成員' }}
              </span>
            </div>
          </div>
          <div v-else class="px-4 py-8 text-sm text-slate-400 text-center">
            尚未指定參與者
          </div>
        </BaseCard>
      </div>

      <!-- Action buttons -->
      <div class="space-y-3 pt-2">
        <button
          @click="onShare"
          :disabled="sharing"
          class="w-full bg-brand-600 hover:bg-brand-700 text-white rounded-xl py-3.5 font-bold shadow-md shadow-brand-500/20 active:scale-98 disabled:opacity-50 transition-all btn-press flex items-center justify-center gap-2"
        >
          <span class="text-base">{{ sharing ? '⏳' : '📤' }}</span>
          <span>{{ sharing ? '小卡發送中…' : '分享回顧小卡到 LINE 群組' }}</span>
        </button>

        <router-link
          v-if="auth.role === 'admin'"
          :to="`/admin/trips/${route.params.id}`"
          class="block w-full text-center bg-slate-800 hover:bg-slate-900 text-white rounded-xl py-3 font-semibold shadow-sm active:scale-98 transition-all btn-press"
        >
          ⚙️ 管理參與名單 / 發放勳章
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import { emojiFor, labelFor } from '@/constants/tripTypes'
import { rarityOf } from '@/constants/rarity'
import { useAuthStore } from '@/stores/auth'
import { buildTripFlex } from '@/utils/flexTripCard'
import { shareFlexMessage } from '@/utils/liffShare'
import { useToast } from '@/composables/useToast'
import BaseCard from '@/components/BaseCard.vue'
import SectionHeader from '@/components/SectionHeader.vue'

const route = useRoute()
const auth = useAuthStore()
const toast = useToast()
const detail = ref<any>(null)
const loading = ref(true)
const sharing = ref(false)

async function onShare() {
  if (!detail.value || sharing.value) return
  sharing.value = true
  try {
    const res = await shareFlexMessage(buildTripFlex(detail.value))
    if (res.success) toast.success('已分享回顧小卡 🎉')
    else if (res.mode === 'picker') toast.error('已取消分享')
  } catch (e: any) {
    toast.error(e?.message || '分享失敗，請稍後再試')
  } finally {
    sharing.value = false
  }
}

const rarity = computed(() => rarityOf(detail.value?.trip?.rarity))

const dateRange = computed(() => {
  const t = detail.value?.trip
  if (!t?.start_date) return ''
  const fmt = (ts: number) => {
    const d = new Date(ts * 1000)
    return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
  }
  const start = fmt(t.start_date)
  if (!t.end_date || t.end_date === t.start_date) return start
  return `${start} – ${fmt(t.end_date)}`
})

onMounted(async () => {
  try { detail.value = await api.tripDetail(route.params.id as string) }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
