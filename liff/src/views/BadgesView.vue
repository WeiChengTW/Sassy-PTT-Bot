<template>
  <div>
    <h1 class="text-xl font-bold mb-4">🏅 我的徽章</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="badges.length === 0" class="text-center py-8 text-gray-400">
      尚未獲得徽章
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