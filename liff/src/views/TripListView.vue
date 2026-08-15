<template>
  <div>
    <h1 class="text-xl font-bold mb-4">🧳 旅行列表</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="trips.length === 0" class="text-center py-8 text-gray-400">尚無旅行紀錄</div>
    <template v-else>
      <!-- 類型過濾 -->
      <div v-if="typeFilters.length" class="flex flex-wrap gap-2 mb-3">
        <button type="button" @click="activeType = ''"
                class="rounded-full px-3 py-1 text-xs border"
                :class="activeType === '' ? 'bg-blue-600 text-white border-blue-600' : 'bg-gray-100 text-gray-600 border-gray-200'">
          全部
        </button>
        <button v-for="ty in typeFilters" :key="ty" type="button" @click="activeType = ty"
                class="rounded-full px-3 py-1 text-xs border"
                :class="activeType === ty ? 'bg-blue-600 text-white border-blue-600' : 'bg-gray-100 text-gray-600 border-gray-200'">
          {{ emojiFor(ty) }} {{ labelFor(ty) }}
        </button>
      </div>

      <div class="space-y-3">
        <router-link v-for="t in filteredTrips" :key="t.id" :to="`/trips/${t.id}`"
                     class="block bg-white rounded-xl shadow p-4">
          <div class="flex items-center gap-2">
            <span class="text-2xl">{{ t.badge_emoji }}</span>
            <div class="flex-1 min-w-0">
              <p class="font-semibold">{{ t.title }}</p>
              <p class="text-xs text-gray-400">{{ t.location }}</p>
              <p v-if="t.trip_types && t.trip_types.length" class="mt-1 text-base leading-none">
                <span v-for="ty in t.trip_types" :key="ty" class="mr-0.5">{{ emojiFor(ty) }}</span>
              </p>
            </div>
            <span class="text-xs px-2 py-1 rounded-full shrink-0"
                  :class="t.status === 'ended' ? 'bg-gray-100 text-gray-500' : 'bg-blue-100 text-blue-600'">
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

const trips = ref<any[]>([])
const loading = ref(true)
const activeType = ref('')

const typeFilters = computed(() => {
  const seen = new Set<string>()
  for (const t of trips.value) for (const ty of (t.trip_types || [])) seen.add(ty)
  return [...seen]
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