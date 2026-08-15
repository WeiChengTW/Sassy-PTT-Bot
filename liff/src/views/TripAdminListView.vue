<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-xl font-bold">🛠️ 旅行管理</h1>
      <router-link to="/admin/trips/new"
                   class="bg-blue-600 text-white text-sm px-3 py-1.5 rounded-lg">
        + 新增旅行
      </router-link>
    </div>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else class="space-y-3">
      <router-link v-for="t in trips" :key="t.id" :to="`/admin/trips/${t.id}`"
                   class="block rounded-2xl border p-4 shadow-sm transition-all"
                   :class="rarityOf(t.rarity).card">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center text-2xl flex-shrink-0"
               :class="rarityOf(t.rarity).icon">
            {{ t.badge_emoji }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <p class="font-bold text-sm truncate" :class="rarityOf(t.rarity).name">{{ t.title }}</p>
              <span class="text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0"
                    :class="rarityOf(t.rarity).pill">
                {{ rarityOf(t.rarity).zh }}
              </span>
            </div>
            <p class="text-xs mt-0.5 truncate" :class="rarityOf(t.rarity).date">{{ t.location || '群組回憶' }}</p>
          </div>
          <span class="text-xs text-gray-500 font-medium">{{ t.status === 'ended' ? '已結束' : '進行中' }}</span>
        </div>
      </router-link>
      <div v-if="trips.length === 0" class="text-center py-8 text-gray-400">尚無旅行</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import { rarityOf } from '@/constants/rarity'

const trips = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try { trips.value = await api.trips() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
