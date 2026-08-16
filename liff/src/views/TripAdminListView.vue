<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
        <span>🛠️ 活動與旅行後台</span>
      </h1>
      <router-link
        to="/admin/trips/new"
        class="bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold px-3.5 py-2 rounded-xl shadow-sm transition-all btn-press inline-flex items-center gap-1"
      >
        <span>➕</span>
        <span>新增旅行</span>
      </router-link>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 3" :key="i" class="skeleton h-20 rounded-2xl" />
    </div>

    <EmptyState
      v-else-if="trips.length === 0"
      icon="🛠️"
      title="尚無旅行資料"
      description="目前沒有建立任何群組旅行紀錄"
    />

    <div v-else class="space-y-3 stagger">
      <router-link
        v-for="t in trips"
        :key="t.id"
        :to="`/admin/trips/${t.id}`"
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import { rarityOf } from '@/constants/rarity'
import EmptyState from '@/components/EmptyState.vue'

const trips = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try { trips.value = await api.trips() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
