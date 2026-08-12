<template>
  <div class="min-h-screen bg-gray-50">
    <nav v-if="auth.initialized" class="bg-white border-b px-4 py-2 flex gap-4 text-sm">
      <router-link to="/" class="hover:text-blue-600">儀表板</router-link>
      <router-link to="/trips" class="hover:text-blue-600">旅行</router-link>
      <router-link to="/badges" class="hover:text-blue-600">徽章</router-link>
      <router-link v-if="auth.role === 'admin'" to="/admin" class="hover:text-red-600 font-medium">管理</router-link>
    </nav>
    <main class="p-4">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
</script>