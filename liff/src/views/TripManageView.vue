<template>
  <div class="space-y-6">
    <button
      @click="$router.back()"
      class="text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors inline-flex items-center gap-1 btn-press px-2.5 py-1.5 rounded-xl bg-white border border-slate-200"
    >
      <span>← 返回</span>
    </button>

    <div v-if="loading" class="space-y-4">
      <div class="skeleton h-32 rounded-2xl" />
      <div class="skeleton h-48 rounded-2xl" />
    </div>

    <div v-else-if="detail" class="space-y-6">
      <!-- 資訊卡片 -->
      <BaseCard class="p-5 card-rise">
        <!-- 檢視模式 -->
        <div v-if="!isEditing">
          <div class="flex items-start justify-between gap-2">
            <h1 class="text-xl font-bold tracking-tight text-slate-900">{{ detail.trip.title }}</h1>
            <button
              @click="startEdit"
              class="text-xs font-bold text-brand-600 hover:text-brand-700 px-3 py-1.5 bg-brand-50 hover:bg-brand-100 rounded-xl shrink-0 transition-colors btn-press"
            >
              ✏️ 編輯資訊
            </button>
          </div>
          <p class="text-slate-500 text-xs font-medium mt-1">📍 {{ detail.trip.location || '無指定地點' }}</p>
          
          <div v-if="detail.trip.trip_types && detail.trip.trip_types.length" class="flex flex-wrap gap-1.5 mt-3">
            <span
              v-for="ty in detail.trip.trip_types"
              :key="ty"
              class="inline-flex items-center gap-1 rounded-lg bg-brand-50/80 text-brand-700 border border-brand-100 px-2 py-0.5 text-xs font-medium"
            >
              {{ emojiFor(ty) }} {{ labelFor(ty) }}
            </span>
          </div>

          <div class="flex items-center gap-2 text-xs mt-3 pt-3 border-t border-slate-100">
            <span class="font-medium text-slate-600">
              狀態：
              <span :class="detail.trip.status === 'ended' ? 'text-slate-400' : 'text-brand-600 font-bold'">
                {{ detail.trip.status === 'ended' ? '已結束' : '進行中 🔥' }}
              </span>
            </span>
            <span
              v-if="detail.trip.rarity"
              class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold shadow-2xs"
              :class="rarity.pill"
            >
              {{ rarity.zh }}
            </span>
          </div>
        </div>

        <!-- 編輯模式 -->
        <div v-else class="space-y-4">
          <div class="flex gap-3 items-start">
            <div class="w-18 shrink-0">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Emoji</label>
              <input
                v-model="editForm.custom_emoji"
                class="w-full bg-slate-50 border border-slate-200 rounded-xl px-2 py-2 text-center text-xl focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white"
                placeholder="🎒"
              />
            </div>
            <div class="flex-1 min-w-0">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">旅行名稱 *</label>
              <input
                v-model="editForm.title"
                class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white"
                placeholder="例如：墾丁三日遊"
              />
            </div>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">地點</label>
            <input
              v-model="editForm.location"
              class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white"
              placeholder="例如：墾丁"
            />
          </div>

          <!-- 日期編輯 -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">開始日期 *</label>
              <input
                v-model="editForm.startDate"
                type="date"
                required
                class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white"
              />
            </div>
            <div>
              <label class="flex items-center gap-1 text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                結束日期
                <span class="text-[10px] text-slate-400 font-normal">（留空=當天）</span>
              </label>
              <input
                v-model="editForm.endDate"
                type="date"
                :min="editForm.startDate || undefined"
                class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white"
              />
            </div>
          </div>

          <div v-if="tripKindLabel" class="text-xs text-slate-400">
            目前分類：<span :class="tripKindLabel.color">{{ tripKindLabel.text }}</span>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">類型標籤（可複選）</label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="t in TRIP_TYPES"
                :key="t.value"
                type="button"
                @click="toggleType(t.value)"
                class="rounded-full px-3 py-1.5 text-xs font-semibold border transition-all duration-150 btn-press"
                :class="editForm.types.includes(t.value)
                  ? 'bg-brand-600 text-white border-brand-600 shadow-sm'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'"
              >
                {{ t.emoji }} {{ t.label }}
              </button>
            </div>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">稀有度等級</label>
            <div class="grid grid-cols-5 gap-1.5">
              <button
                v-for="r in rarityOptions"
                :key="r.key"
                type="button"
                @click="editForm.rarity = r.key"
                class="py-1.5 text-xs rounded-xl border font-bold transition-all btn-press"
                :class="editForm.rarity === r.key ? `${r.pill} border-current shadow-sm` : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'"
              >
                {{ r.zh }}
              </button>
            </div>
          </div>

          <div class="flex items-center gap-2 pt-2 border-t border-slate-100">
            <button
              @click="saveEdit"
              :disabled="saving || !editForm.title.trim()"
              class="flex-1 bg-brand-600 hover:bg-brand-700 text-white text-xs py-2.5 rounded-xl font-bold disabled:opacity-50 transition-all btn-press shadow-sm"
            >
              {{ saving ? '儲存中...' : '儲存變更' }}
            </button>
            <button
              @click="isEditing = false"
              class="px-4 py-2.5 border border-slate-200 text-xs font-semibold rounded-xl text-slate-600 hover:bg-slate-50 transition-all btn-press"
            >
              取消
            </button>
          </div>
        </div>
      </BaseCard>

      <!-- 參與人勾選卡片 -->
      <BaseCard class="p-5 card-rise">
        <SectionHeader
          title="參與人員名單"
          icon="👥"
          :subtitle="`已選 ${selected.size} 人`"
          class="!mt-0 !mb-3"
        />

        <div v-if="membersLoading" class="text-xs text-slate-400 py-3">載入群組成員中...</div>
        <div v-else class="grid grid-cols-2 gap-2 max-h-60 overflow-y-auto no-scrollbar pr-1">
          <label
            v-for="m in members"
            :key="m.user_id"
            class="flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium cursor-pointer select-none transition-all duration-150"
            :class="selected.has(m.user_id) ? 'border-brand-300 bg-brand-50/80 text-brand-900 font-semibold' : 'border-slate-200 hover:bg-slate-50 text-slate-700'"
          >
            <input
              type="checkbox"
              :checked="selected.has(m.user_id)"
              @change="toggle(m.user_id)"
              class="accent-brand-600 rounded"
            />
            <span class="truncate" :class="m.resolved ? '' : 'text-slate-400'">
              {{ m.display_name }}
              <span v-if="!m.resolved" class="text-[10px]">（待接回）</span>
            </span>
          </label>
        </div>

        <button
          v-if="detail.trip.status !== 'ended'"
          @click="saveAndAward"
          :disabled="actionLoading || selected.size === 0"
          class="mt-4 w-full bg-purple-600 hover:bg-purple-700 text-white rounded-xl py-3 text-sm font-bold shadow-md shadow-purple-500/20 disabled:opacity-50 transition-all btn-press"
        >
          💾 儲存名單並結束活動、發放徽章
        </button>
        <button
          v-else
          @click="saveParticipants"
          :disabled="actionLoading"
          class="mt-4 w-full bg-slate-800 hover:bg-slate-900 text-white rounded-xl py-3 text-sm font-semibold disabled:opacity-50 transition-all btn-press"
        >
          💾 更新參與名單
        </button>
      </BaseCard>

      <!-- 手動操作 -->
      <div class="space-y-2.5">
        <button
          v-if="detail.trip.status !== 'ended'"
          @click="endTrip"
          :disabled="actionLoading"
          class="w-full bg-accent-500 hover:bg-accent-600 text-white rounded-xl py-3 text-sm font-bold shadow-sm disabled:opacity-50 transition-all btn-press"
        >
          🏁 僅結束旅行（不發徽章）
        </button>
        <button
          v-if="detail.trip.status === 'ended'"
          @click="awardBadges"
          :disabled="actionLoading"
          class="w-full border border-purple-300 text-purple-700 hover:bg-purple-50 rounded-xl py-3 text-sm font-bold disabled:opacity-50 transition-all btn-press"
        >
          🏅 重新發放徽章
        </button>
      </div>

      <p v-if="message" class="text-center mt-3 text-xs font-bold text-success-600">{{ message }}</p>
      <p v-if="error" class="text-center mt-3 text-xs font-bold text-danger-600">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import { rarityOf } from '@/constants/rarity'
import { TRIP_TYPES, emojiFor, labelFor } from '@/constants/tripTypes'
import BaseCard from '@/components/BaseCard.vue'
import SectionHeader from '@/components/SectionHeader.vue'

const route = useRoute()
const tripId = route.params.id as string

const detail = ref<any>(null)
const loading = ref(true)
const membersLoading = ref(true)
const actionLoading = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const editForm = ref({
  title: '',
  location: '',
  rarity: 'common',
  types: [] as string[],
  custom_emoji: '',
  startDate: '',
  endDate: '',
})
const members = ref<{ user_id: string; display_name: string; resolved: number }[]>([])
const selected = ref<Set<string>>(new Set())
const message = ref('')
const error = ref('')

const rarity = computed(() => rarityOf(detail.value?.trip?.rarity))

const tripKindLabel = computed(() => {
  const sd = editForm.value.startDate
  const ed = editForm.value.endDate
  if (!sd) return null
  if (ed && ed !== sd) return { text: '多日旅行 🧳', color: 'text-brand-600 font-bold' }
  return { text: '當天事件 ⚡', color: 'text-accent-600 font-bold' }
})

const rarityOptions = [
  { key: 'common', zh: '普通', pill: 'bg-slate-100 text-slate-700' },
  { key: 'rare', zh: '稀有', pill: 'bg-sky-100 text-sky-700' },
  { key: 'super_rare', zh: '極稀有', pill: 'bg-accent-100 text-accent-700' },
  { key: 'epic', zh: '史詩', pill: 'bg-purple-100 text-purple-700' },
  { key: 'legendary', zh: '傳說', pill: 'bg-rose-100 text-rose-700' },
]

function toDateInput(ts: number | null | undefined) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function toggleType(typeVal: string) {
  const i = editForm.value.types.indexOf(typeVal)
  if (i >= 0) editForm.value.types.splice(i, 1)
  else editForm.value.types.push(typeVal)
}

function startEdit() {
  const t = detail.value?.trip || {}
  editForm.value = {
    title: t.title || '',
    location: t.location || '',
    rarity: t.rarity || 'common',
    types: [...(t.trip_types || [])],
    custom_emoji: t.custom_emoji || t.badge_emoji || '',
    startDate: toDateInput(t.start_date),
    endDate: toDateInput(t.end_date),
  }
  isEditing.value = true
}

async function saveEdit() {
  if (!editForm.value.title.trim() || saving.value) return
  saving.value = true
  message.value = ''; error.value = ''
  try {
    const startTs = editForm.value.startDate
      ? Math.floor(new Date(editForm.value.startDate).getTime() / 1000)
      : null
    const endTs = editForm.value.endDate
      ? Math.floor(new Date(editForm.value.endDate).getTime() / 1000)
      : null
    await api.adminUpdateTrip(tripId, {
      title: editForm.value.title.trim(),
      location: editForm.value.location.trim(),
      rarity: editForm.value.rarity,
      types: editForm.value.types,
      custom_emoji: editForm.value.custom_emoji.trim(),
      start_date: startTs,
      end_date: endTs,
    })
    await load()
    isEditing.value = false
    message.value = '旅行資訊修改成功 🎉'
  } catch (e: any) {
    error.value = e.message || '修改失敗'
  } finally {
    saving.value = false
  }
}

function toggle(userId: string) {
  const s = new Set(selected.value)
  s.has(userId) ? s.delete(userId) : s.add(userId)
  selected.value = s
}

async function load() {
  loading.value = true
  try {
    detail.value = await api.tripDetail(tripId)
    selected.value = new Set((detail.value?.participants || []).map((p: any) => p.user_id))
  } finally { loading.value = false }
}

async function loadMembers() {
  membersLoading.value = true
  try { members.value = await api.adminMembers() }
  catch (e: any) { error.value = e.message }
  finally { membersLoading.value = false }
}

async function saveParticipants() {
  message.value = ''; error.value = ''
  await api.adminAddParticipants(tripId, [...selected.value])
  await load()
}

async function saveAndAward() {
  if (!confirm('儲存參與人並結束事件、發放徽章？')) return
  actionLoading.value = true
  message.value = ''; error.value = ''
  try {
    await api.adminAddParticipants(tripId, [...selected.value])
    await api.adminEndTrip(tripId)
    const res = await api.adminAwardBadges(tripId)
    await load()
    message.value = `已結束並發放 ${res.awarded.length} 枚徽章`
  } catch (e: any) { error.value = e.message }
  finally { actionLoading.value = false }
}

async function endTrip() {
  if (!confirm('確定只結束旅行（不發徽章）？')) return
  actionLoading.value = true
  message.value = ''; error.value = ''
  try {
    await api.adminEndTrip(tripId)
    await load()
    message.value = '旅行已結束'
  } catch (e: any) { error.value = e.message }
  finally { actionLoading.value = false }
}

async function awardBadges() {
  actionLoading.value = true
  message.value = ''; error.value = ''
  try {
    const res = await api.adminAwardBadges(tripId)
    message.value = `已發放 ${res.awarded.length} 枚徽章`
  } catch (e: any) { error.value = e.message }
  finally { actionLoading.value = false }
}

onMounted(() => { load(); loadMembers() })
</script>
