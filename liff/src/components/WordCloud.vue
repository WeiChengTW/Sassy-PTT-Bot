<template>
  <div ref="containerRef" class="w-full">
    <svg ref="svgRef" :width="w" :height="h" class="w-full" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

const props = defineProps<{
  words: { text: string; count: number }[]
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)
const w = ref(320)
const h = ref(240)

const PALETTE = ['#2563eb', '#7c3aed', '#db2777', '#059669', '#d97706', '#0891b2', '#dc2626']

async function render() {
  if (!svgRef.value || !containerRef.value || !props.words?.length) return
  w.value = containerRef.value.clientWidth || 320
  await nextTick()

  const [{ default: cloud }, d3] = await Promise.all([
    import('d3-cloud'),
    import('d3'),
  ])

  const counts = props.words.map((d) => d.count)
  const min = Math.min(...counts)
  const max = Math.max(...counts)
  const sizeScale = d3.scaleSqrt().domain([min, max || 1]).range([14, 46])

  const layoutWords = props.words.map((d) => ({
    text: d.text,
    size: sizeScale(d.count),
    count: d.count,
  }))

  const layout = cloud<any>()
    .size([w.value, h.value])
    .words(layoutWords)
    .padding(3)
    .rotate(() => (Math.random() < 0.7 ? 0 : 90))
    .font('sans-serif')
    .fontSize((d: any) => d.size)
    .on('end', draw)

  layout.start()

  function draw(words: any[]) {
    const svg = d3.select(svgRef.value)
    svg.selectAll('*').remove()
    svg
      .append('g')
      .attr('transform', `translate(${w.value / 2},${h.value / 2})`)
      .selectAll('text')
      .data(words)
      .join('text')
      .style('font-size', (d: any) => `${d.size}px`)
      .style('font-weight', '600')
      .style('font-family', 'sans-serif')
      .style('fill', (_d: any, i: number) => PALETTE[i % PALETTE.length])
      .attr('text-anchor', 'middle')
      .attr('transform', (d: any) => `translate(${d.x},${d.y}) rotate(${d.rotate})`)
      .text((d: any) => d.text)
  }
}

let ro: ResizeObserver | null = null

onMounted(() => {
  render()
  if (containerRef.value && 'ResizeObserver' in window) {
    ro = new ResizeObserver(() => render())
    ro.observe(containerRef.value)
  }
})

onUnmounted(() => {
  ro?.disconnect()
})

watch(() => props.words, () => render(), { deep: true })
</script>
