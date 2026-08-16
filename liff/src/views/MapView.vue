<template>
  <div class="flex flex-col h-[calc(100vh-145px)] space-y-3">
    <!-- 頂部資訊與過濾 -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
          <span>🌍 足跡探索地圖</span>
        </h1>
        <p class="text-xs text-slate-400 mt-0.5 font-medium">
          已探索 <span class="font-bold font-mono text-brand-600">{{ mappedTrips.length }}</span> 個地點足跡
        </p>
      </div>
      <button
        @click="fitBounds"
        class="text-xs px-3 py-1.5 bg-white border border-slate-200 rounded-xl shadow-xs font-bold text-slate-600 hover:text-brand-600 hover:border-brand-200 active:scale-95 transition-all btn-press inline-flex items-center gap-1"
      >
        <span>🎯</span>
        <span>全景視角</span>
      </button>
    </div>

    <!-- 地圖容器 -->
    <div class="flex-1 relative rounded-2xl overflow-hidden shadow-card border border-slate-200/80 bg-slate-100 min-h-[350px]">
      <div id="footprint-map" class="w-full h-full z-10" />
      <div v-if="loading" class="absolute inset-0 z-20 bg-white/70 backdrop-blur-xs flex items-center justify-center">
        <div class="text-center">
          <p class="text-3xl animate-bounce">🌍</p>
          <p class="text-xs text-slate-500 font-bold mt-2">載入足跡地圖中...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { api } from '@/api/client'
import { resolveLocationCoords } from '@/constants/locations'
import { rarityOf } from '@/constants/rarity'
import { emojiFor, labelFor } from '@/constants/tripTypes'

const trips = ref<any[]>([])
const loading = ref(true)
let map: L.Map | null = null
let markerLayer: L.LayerGroup | null = null

const mappedTrips = computed(() => {
  return trips.value
    .map((t) => {
      const coords = resolveLocationCoords(t.location, t.title)
      return coords ? { ...t, coords } : null
    })
    .filter(Boolean) as (any & { coords: [number, number] })[]
})

function initMap() {
  const container = document.getElementById('footprint-map')
  if (!container) return

  // 預設中心為台灣
  map = L.map('footprint-map', {
    center: [23.9756, 120.9738],
    zoom: 7,
    zoomControl: false,
  })

  L.control.zoom({ position: 'bottomright' }).addTo(map)

  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 19,
  }).addTo(map)

  markerLayer = L.layerGroup().addTo(map)
  renderMarkers()
}

function renderMarkers() {
  if (!map || !markerLayer) return
  markerLayer.clearLayers()

  const bounds: L.LatLngBounds = L.latLngBounds([])

  mappedTrips.value.forEach((t) => {
    const rarity = rarityOf(t.rarity)
    const emoji = t.custom_emoji || t.badge_emoji || '🎒'

    // 客製 HTML Marker Icon
    const customIcon = L.divIcon({
      className: 'custom-map-pin',
      html: `
        <div class="relative flex items-center justify-center w-11 h-11 rounded-2xl shadow-lift border-2 border-white transition-all hover:scale-115 active:scale-95 cursor-pointer ${rarity.card}">
          <span class="text-2xl leading-none">${emoji}</span>
          <span class="absolute -bottom-1 -right-1 w-3.5 h-3.5 rounded-full border-2 border-white ${rarity.dot}"></span>
        </div>
      `,
      iconSize: [44, 44],
      iconAnchor: [22, 22],
      popupAnchor: [0, -24],
    })

    const marker = L.marker(t.coords, { icon: customIcon })
    
    // Popup 內容
    const dt = t.start_date ? new Date(t.start_date * 1000).toLocaleDateString('zh-TW') : ''
    const tagsHtml = (t.trip_types || [])
      .map((ty: string) => `<span class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-brand-50 text-[10px] text-brand-700 font-semibold border border-brand-100">${emojiFor(ty)} ${labelFor(ty)}</span>`)
      .join(' ')

    const popupContent = `
      <div class="p-1 max-w-[210px] font-sans">
        <div class="flex items-center gap-1.5">
          <span class="text-xl">${emoji}</span>
          <p class="font-bold text-sm text-slate-900 leading-tight">${t.title}</p>
        </div>
        <p class="text-[11px] text-slate-500 font-medium mt-1">📍 ${t.location || '群組回憶'}</p>
        <p class="text-[10px] text-slate-400 font-mono mt-0.5">🗓️ ${dt}</p>
        <div class="mt-2 flex flex-wrap gap-1">${tagsHtml}</div>
        <a href="/trips/${t.id}" class="mt-2.5 block w-full text-center bg-brand-600 hover:bg-brand-700 text-white rounded-xl py-1.5 text-xs font-bold no-underline transition-colors shadow-xs">
          查看事件詳情 →
        </a>
      </div>
    `
    marker.bindPopup(popupContent, { closeButton: false, minWidth: 170 })
    if (markerLayer) {
      markerLayer.addLayer(marker)
    }
    bounds.extend(t.coords)
  })

  if (mappedTrips.value.length && bounds.isValid()) {
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 })
  }
}

function fitBounds() {
  if (!map || !mappedTrips.value.length) return
  const bounds = L.latLngBounds(mappedTrips.value.map((t) => t.coords))
  if (bounds.isValid()) {
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 })
  }
}

onMounted(async () => {
  try {
    trips.value = await api.trips()
    await nextTick()
    initMap()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  if (map) {
    map.remove()
    map = null
  }
})
</script>

<style>
.custom-map-pin {
  background: transparent;
  border: none;
}
.leaflet-popup-content-wrapper {
  border-radius: 1.25rem;
  box-shadow: 0 20px 40px -12px rgba(15, 23, 42, 0.2);
  border: 1px solid rgba(226, 232, 240, 0.8);
  padding: 4px;
}
.leaflet-popup-content {
  margin: 10px 12px;
}
</style>
