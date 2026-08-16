<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
        <span>🧳 群組旅行與活動</span>
      </h1>
      <router-link
        to="/trips/create"
        class="text-xs font-semibold px-3 py-1.5 rounded-xl bg-brand-600 text-white shadow-sm hover:bg-brand-700 active:scale-95 transition-all btn-press inline-flex items-center gap-1"
      >
        <span>➕</span>
        <span>發起旅行</span>
      </router-link>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-3">
      <div class="skeleton h-8 w-full rounded-full" />
      <div v-for="i in 3" :key="i" class="skeleton h-20 rounded-2xl" />
    </div>

    <EmptyState
      v-else-if="trips.length === 0"
      icon="🧳"
      title="尚無旅行紀錄"
      description="快來發起第一場群組旅行或聚會，紀錄精彩回憶！"
    >
      <template #action>
        <router-link
          to="/trips/create"
          class="text-xs font-bold px-4 py-2 rounded-xl bg-brand-600 text-white shadow-sm btn-press inline-block"
        >
          立即發起旅行
        </router-link>
      </template>
    </EmptyState>

    <template v-else>
      <!-- 類型過濾 -->
      <div v-if="typeFilters.length" class="mb-4">
        <ChipFilter
          v-model="activeType"
          :options="chipOptions"
          all-label="全部類型"
        />
      </div>

      <div class="space-y-3 stagger">
        <router-link
          v-for="t in filteredTrips"
          :key="t.id"
          :to="`/trips/${t.id}`"
          class="block rounded-2xl border p-4 shadow-card transition-all duration-200 active:scale-[0.98] card-rise"
          :class="rarityOf(t.rarity).card"
        >
          <div class="flex items-center gap-3.5">
            <div
              class="w-12 h-12 rounded-2xl flex items-center justify-center text-2xl shrink-0 shadow-inner"
              :class="rarityOf(t.rarity).icon"
            >
              {{ t.badge_emoji }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <p class="font-bold text-sm truncate" :class="rarityOf(t.rarity).name">
                  {{ t.title }}
                </p>
                <span
                  class="text-[10px] px-2 py-0.5 rounded-full font-bold shrink-0 shadow-2xs"
                  :class="rarityOf(t.rarity).pill"
                >
                  {{ rarityOf(t.rarity).zh }}
                </span>
              </div>
              <p class="text-xs mt-0.5 truncate font-medium" :class="rarityOf(t.rarity).date">
                📍 {{ t.location || '群組回憶' }}
              </p>
              <p v-if="t.trip_types && t.trip_types.length" class="mt-1 text-xs leading-none flex gap-1">
                <span
                  v-for="ty in t.trip_types"
                  :key="ty"
                  class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-white/70 text-[10px] font-medium text-slate-600"
                >
                  {{ emojiFor(ty) }} {{ labelFor(ty) }}
                </span>
              </p>
            </div>
            <span
              class="text-[11px] px-2.5 py-1 rounded-full shrink-0 font-bold"
              :class="t.status === 'ended' ? 'bg-slate-200/80 text-slate-600' : 'bg-brand-600 text-white shadow-sm'"
            >
              {{ t.status === 'ended' ? '已結束' : '進行中' }}
            </span>
          </div>
        </router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client'
import { emojiFor, labelFor } from '@/constants/tripTypes'
import { rarityOf } from '@/constants/rarity'
import ChipFilter from '@/components/ChipFilter.vue'
import EmptyState from '@/components/EmptyState.vue'

const trips = ref<any[]>([])
const loading = ref(true)
const activeType = ref('')

const typeFilters = computed(() => {
  const seen = new Set<string>()
  for (const t of trips.value) for (const ty of (t.trip_types || [])) seen.add(ty)
  return [...seen]
})

const chipOptions = computed(() => {
  return typeFilters.value.map((ty) => ({
    value: ty,
    label: labelFor(ty),
    emoji: emojiFor(ty),
  }))
})

const filteredTrips = computed(() =>
  activeType.value
    ? trips.value.filter((t) => (t.trip_types || []).includes(activeType.value))
    : trips.value,
)

onMounted(async () => {
  try { trips.value = await api.trips() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
