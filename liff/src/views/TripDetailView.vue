<template>
  <div>
    <button @click="$router.back()" class="text-sm text-gray-500 mb-4">← 返回</button>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="detail">
      <div class="bg-white rounded-xl shadow p-4 mb-4">
        <div class="flex items-start justify-between gap-2">
          <h1 class="text-xl font-bold">{{ detail.trip.title }}</h1>
          <span v-if="detail.trip.rarity"
                class="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium"
                :class="rarity.pill">
            {{ rarity.emoji }} {{ rarity.zh }}
          </span>
        </div>
        <p v-if="detail.trip.location" class="text-gray-500 text-sm">{{ detail.trip.location }}</p>
        <p v-if="dateRange" class="text-gray-500 text-sm mt-0.5">🗓️ {{ dateRange }}</p>
        <div v-if="detail.trip.trip_types && detail.trip.trip_types.length"
             class="flex flex-wrap gap-1.5 mt-2">
          <span v-for="ty in detail.trip.trip_types" :key="ty"
                class="inline-flex items-center gap-1 rounded-full bg-blue-50 text-blue-600 px-2.5 py-0.5 text-xs">
            {{ emojiFor(ty) }} {{ labelFor(ty) }}
          </span>
        </div>
        <p class="text-xs text-gray-400 mt-1">
          狀態：{{ detail.trip.status === 'ended' ? '已結束' : '進行中' }}
          · 訊息數 {{ detail.stats.message_count }}
        </p>
      </div>

      <h2 class="font-semibold mb-2">👥 參與者（{{ detail.participants.length }}）</h2>
      <div v-if="detail.participants.length" class="bg-white rounded-xl shadow divide-y mb-4">
        <div v-for="p in detail.participants" :key="p.user_id" class="px-4 py-2 text-sm">
          {{ p.user_name || p.user_id }}
          <span class="text-xs text-gray-400 ml-2">{{ p.role || '成員' }}</span>
        </div>
      </div>
      <p v-else class="text-sm text-gray-400 bg-white rounded-xl shadow px-4 py-3 mb-4">
        尚未指定參與者
      </p>

      <button @click="onShare" :disabled="sharing"
              class="w-full bg-blue-600 text-white rounded-xl py-3 font-medium disabled:opacity-50 mb-3">
        {{ sharing ? '發送中…' : '📤 分享回顧小卡到群組' }}
      </button>

      <router-link v-if="auth.role === 'admin'" :to="`/admin/trips/${route.params.id}`"
                   class="block w-full text-center bg-gray-800 text-white rounded-xl py-3 font-medium">
        ⚙️ 管理參與人 / 發徽章
      </router-link>
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