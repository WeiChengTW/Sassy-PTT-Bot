<template>
  <div class="flex flex-col h-[calc(100vh-140px)]">
    <!-- 頂部資訊與過濾 -->
    <div class="mb-3 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-900">🌍 足跡地圖</h1>
        <p class="text-xs text-gray-400 mt-0.5">
          已探索 <span class="font-semibold text-blue-600">{{ mappedTrips.length }}</span> 個地點足跡
        </p>
      </div>
      <button @click="fitBounds" class="text-xs px-2.5 py-1.5 bg-white border border-gray-200 rounded-lg shadow-sm font-medium text-gray-600 hover:text-blue-600 active:scale-95 transition-all">
        🎯 縮放全景
      </button>
    </div>

    <!-- 地圖容器 -->
    <div class="flex-1 relative rounded-2xl overflow-hidden shadow-md border border-gray-200 bg-slate-100 min-h-[350px]">
      <div id="footprint-map" class="w-full h-full z-10" />
      <div v-if="loading" class="absolute inset-0 z-20 bg-white/70 backdrop-blur-sm flex items-center justify-center">
        <div class="text-center">
          <p class="text-2xl animate-bounce">🌍</p>
          <p class="text-xs text-gray-500 font-medium mt-1">載入足跡地圖中...</p>
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

  // 使用高質感無標籤底圖 + 標籤層
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
        <div class="relative flex items-center justify-center w-10 h-10 rounded-2xl shadow-lg border-2 border-white transition-transform hover:scale-110 active:scale-95 cursor-pointer ${rarity.card}">
          <span class="text-xl leading-none">${emoji}</span>
          <span class="absolute -bottom-1 -right-1 w-3 h-3 rounded-full border border-white ${rarity.dot}"></span>
        </div>
      `,
      iconSize: [40, 40],
      iconAnchor: [20, 20],
      popupAnchor: [0, -22],
    })

    const marker = L.marker(t.coords, { icon: customIcon })
    
    // Popup 內容
    const dt = t.start_date ? new Date(t.start_date * 1000).toLocaleDateString('zh-TW') : ''
    const tagsHtml = (t.trip_types || [])
      .map((ty: string) => `<span class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-blue-50 text-[10px] text-blue-600 font-medium">${emojiFor(ty)} ${labelFor(ty)}</span>`)
      .join(' ')

    const popupContent = `
      <div class="p-1 max-w-[200px] font-sans">
        <div class="flex items-center gap-1.5">
          <span class="text-base">${emoji}</span>
          <p class="font-bold text-sm text-gray-900 leading-tight">${t.title}</p>
        </div>
        <p class="text-[11px] text-gray-500 mt-1">📍 ${t.location || '群組回憶'}</p>
        <p class="text-[10px] text-gray-400 mt-0.5">🗓️ ${dt}</p>
        <div class="mt-1.5 flex flex-wrap gap-1">${tagsHtml}</div>
        <a href="/trips/${t.id}" class="mt-2 block w-full text-center bg-blue-600 text-white rounded-lg py-1 text-[11px] font-medium no-underline hover:bg-blue-700">
          查看事件詳情 →
        </a>
      </div>
    `
    marker.bindPopup(popupContent, { closeButton: false, minWidth: 160 })
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
  border-radius: 1rem;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(0, 0, 0, 0.05);
}
.leaflet-popup-content {
  margin: 10px 12px;
}
</style>
