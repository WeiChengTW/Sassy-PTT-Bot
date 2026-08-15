<template>
  <span class="tabular-nums font-mono">{{ displayValue }}</span>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

const props = withDefaults(
  defineProps<{
    value: number
    duration?: number
    format?: (val: number) => string
  }>(),
  {
    duration: 600,
  }
)

const displayValue = ref('')

function animate(start: number, end: number) {
  const startTime = performance.now()
  const step = (currentTime: number) => {
    const progress = Math.min((currentTime - startTime) / props.duration, 1)
    // easeOutExpo
    const ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress)
    const current = Math.round(start + (end - start) * ease)
    
    if (props.format) {
      displayValue.value = props.format(current)
    } else {
      displayValue.value = current.toLocaleString()
    }

    if (progress < 1) {
      requestAnimationFrame(step)
    }
  }
  requestAnimationFrame(step)
}

watch(
  () => props.value,
  (newVal, oldVal) => {
    animate(oldVal || 0, newVal)
  }
)

onMounted(() => {
  animate(0, props.value)
})
</script>
