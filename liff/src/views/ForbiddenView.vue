<template>
  <div class="py-20">
    <EmptyState
      icon="🚫"
      title="您尚未加入此群組"
      description="本統計數據專為群組成員提供，請先透過 LINE 加入群組後再開啟此頁面！"
    />
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/EmptyState.vue'
</script>
