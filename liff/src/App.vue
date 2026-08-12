<template>
  <div class="min-h-screen bg-gray-50 pb-16">
    <main class="p-4">
      <router-view />
    </main>

    <nav v-if="auth.initialized"
         class="fixed bottom-0 inset-x-0 bg-white border-t flex justify-around text-xs py-1 z-50">
      <router-link to="/" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">📊</span><span>儀表板</span>
      </router-link>
      <router-link to="/leaderboard" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">🏆</span><span>排行榜</span>
      </router-link>
      <router-link to="/interactions" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">🤝</span><span>互動</span>
      </router-link>
      <router-link to="/topics" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">🏷️</span><span>話題</span>
      </router-link>
      <router-link to="/profile" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">👤</span><span>個人</span>
      </router-link>
      <router-link to="/trips" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">🧳</span><span>旅行</span>
      </router-link>
      <router-link v-if="auth.role === 'admin'" to="/admin"
                   class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-red-500">
        <span class="text-lg">🛠️</span><span>管理</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
</script>
