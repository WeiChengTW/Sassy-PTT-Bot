<template>
  <div>
    <h1 class="text-xl font-bold mb-4 text-gray-900">我的徽章</h1>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 3" :key="i"
           class="rounded-2xl border border-gray-200 p-4 flex items-center gap-4">
        <div class="skeleton w-14 h-14 rounded-2xl flex-shrink-0" />
        <div class="flex-1 space-y-2">
          <div class="skeleton h-4 rounded-full w-2/3" />
          <div class="skeleton h-3 rounded-full w-1/3" />
        </div>
      </div>
    </div>

    <div v-else-if="badges.length === 0"
         class="text-center py-16 text-gray-400">
      <div class="text-4xl mb-3">🏅</div>
      <p class="text-sm">尚未獲得徽章</p>
      <p class="text-xs mt-1 text-gray-300">參與旅行即可解鎖</p>
    </div>

    <div v-else class="space-y-3">
      <BadgeCard v-for="b in badges" :key="b.badge_id" :badge="b" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import BadgeCard from '@/components/BadgeCard.vue'

const auth = useAuthStore()
const badges = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try { badges.value = await api.badges(auth.userId) }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
