<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
        <span>🏅 我的成就勳章</span>
      </h1>
      <span v-if="badges.length" class="text-xs font-mono font-bold text-brand-600 bg-brand-50 px-2.5 py-1 rounded-full">
        已解鎖 {{ badges.length }} 枚
      </span>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 3" :key="i"
           class="rounded-2xl border border-slate-100 bg-white p-4 flex items-center gap-4">
        <div class="skeleton w-14 h-14 rounded-2xl shrink-0" />
        <div class="flex-1 space-y-2">
          <div class="skeleton h-4 rounded-full w-2/3" />
          <div class="skeleton h-3 rounded-full w-1/3" />
        </div>
      </div>
    </div>

    <EmptyState
      v-else-if="badges.length === 0"
      icon="🏅"
      title="尚未獲得任何勳章"
      description="參與群組旅行與活動，即可解鎖各式專屬稀有勳章！"
    />

    <div v-else class="space-y-3 stagger">
      <BadgeCard v-for="b in badges" :key="b.badge_id" :badge="b" class="card-rise" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import BadgeCard from '@/components/BadgeCard.vue'
import EmptyState from '@/components/EmptyState.vue'

const auth = useAuthStore()
const badges = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try { badges.value = await api.badges(auth.userId) }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
