<template>
  <Transition name="toast">
    <div v-if="toast.state.visible"
         class="fixed z-[60] bottom-24 inset-x-0 flex justify-center px-4 pointer-events-none">
      <div class="max-w-sm w-fit text-white text-sm font-semibold rounded-2xl shadow-pop px-4 py-2.5 flex items-center gap-2 backdrop-blur-md"
           :class="toast.state.type === 'success' ? 'bg-success-600/95 border border-success-400/30' : 'bg-danger-600/95 border border-danger-400/30'"
           role="status" aria-live="polite">
        <span class="text-base">{{ toast.state.type === 'success' ? '✅' : '⚠️' }}</span>
        <span>{{ toast.state.message }}</span>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const toast = useToast()
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    transition: opacity 0.1s linear;
    transform: none !important;
  }
}
</style>
