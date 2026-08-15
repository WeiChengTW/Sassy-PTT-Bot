<template>
  <div>
    <button @click="$router.back()" class="text-sm text-gray-500 mb-4">← 返回</button>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="detail">
      <div class="bg-white rounded-xl shadow p-4 mb-4">
        <!-- 檢視模式 -->
        <div v-if="!isEditing">
          <div class="flex items-start justify-between gap-2">
            <h1 class="text-xl font-bold text-gray-900">{{ detail.trip.title }}</h1>
            <button @click="startEdit" class="text-xs text-blue-600 hover:text-blue-800 font-medium px-2.5 py-1 bg-blue-50 rounded-lg shrink-0">
              ✏️ 編輯資訊
            </button>
          </div>
          <p class="text-gray-500 text-sm mt-1">📍 {{ detail.trip.location || '無指定地點' }}</p>
          <div class="flex items-center gap-2 text-xs mt-2">
            <span>狀態：
              <span :class="detail.trip.status === 'ended' ? 'text-gray-400' : 'text-blue-600'">
                {{ detail.trip.status === 'ended' ? '已結束' : '進行中' }}
              </span>
            </span>
            <span v-if="detail.trip.rarity"
                  class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-medium"
                  :class="rarity.pill">
              {{ rarity.zh }}
            </span>
          </div>
        </div>

        <!-- 編輯模式 -->
        <div v-else class="space-y-3">
          <div>
            <label class="block text-xs font-semibold text-gray-500 mb-1">旅行名稱 *</label>
            <input v-model="editForm.title" class="w-full border border-gray-300 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-500" placeholder="例如：墾丁三日遊" />
          </div>
          <div>
            <label class="block text-xs font-semibold text-gray-500 mb-1">地點</label>
            <input v-model="editForm.location" class="w-full border border-gray-300 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-500" placeholder="例如：墾丁" />
          </div>
          <div>
            <label class="block text-xs font-semibold text-gray-500 mb-1">稀有度等級</label>
            <div class="grid grid-cols-5 gap-1.5">
              <button v-for="r in rarityOptions" :key="r.key" type="button"
                      @click="editForm.rarity = r.key"
                      class="py-1.5 text-xs rounded-lg border font-medium transition-all"
                      :class="editForm.rarity === r.key ? `${r.pill} border-current shadow-sm` : 'bg-gray-50 text-gray-600 border-gray-200'">
                {{ r.zh }}
              </button>
            </div>
          </div>
          <div class="flex items-center gap-2 pt-1">
            <button @click="saveEdit" :disabled="saving || !editForm.title.trim()"
                    class="flex-1 bg-blue-600 text-white text-xs py-2 rounded-lg font-medium disabled:opacity-50">
              {{ saving ? '儲存中...' : '儲存變更' }}
            </button>
            <button @click="isEditing = false" class="px-3 py-2 border border-gray-300 text-xs rounded-lg text-gray-600">
              取消
            </button>
          </div>
        </div>
      </div>

      <!-- 參與人選擇：從群組名單勾選 -->
      <div class="bg-white rounded-xl shadow p-4 mb-4">
        <h2 class="font-semibold mb-3">👥 參與人（已選 {{ selected.size }}）</h2>
        <div v-if="membersLoading" class="text-sm text-gray-400 py-2">載入名單中...</div>
        <div v-else class="grid grid-cols-2 gap-2">
          <label v-for="m in members" :key="m.user_id"
                 class="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm cursor-pointer select-none"
                 :class="selected.has(m.user_id) ? 'border-blue-400 bg-blue-50' : 'border-gray-200'">
            <input type="checkbox" :checked="selected.has(m.user_id)"
                   @change="toggle(m.user_id)" class="accent-blue-500" />
            <span class="truncate" :class="m.resolved ? '' : 'text-gray-400'">
              {{ m.display_name }}
              <span v-if="!m.resolved" class="text-[10px]">（待接回）</span>
            </span>
          </label>
        </div>

        <button v-if="detail.trip.status !== 'ended'" @click="saveAndAward"
                :disabled="actionLoading || selected.size === 0"
                class="mt-4 w-full bg-purple-600 text-white rounded-xl py-3 font-medium disabled:opacity-50">
          💾 儲存參與人並發徽章
        </button>
        <button v-else @click="saveParticipants"
                :disabled="actionLoading"
                class="mt-4 w-full bg-gray-800 text-white rounded-xl py-3 font-medium disabled:opacity-50">
          💾 更新參與人
        </button>
      </div>

      <!-- 手動後備動作 -->
      <div class="space-y-2">
        <button v-if="detail.trip.status !== 'ended'" @click="endTrip"
                :disabled="actionLoading"
                class="w-full bg-orange-500 text-white rounded-xl py-2.5 text-sm font-medium disabled:opacity-50">
          🏁 只結束旅行（不發徽章）
        </button>
        <button v-if="detail.trip.status === 'ended'" @click="awardBadges"
                :disabled="actionLoading"
                class="w-full border border-purple-300 text-purple-700 rounded-xl py-2.5 text-sm font-medium disabled:opacity-50">
          🏅 重新發放徽章
        </button>
      </div>

      <p v-if="message" class="text-center mt-3 text-sm text-green-600">{{ message }}</p>
      <p v-if="error" class="text-center mt-3 text-sm text-red-500">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import { rarityOf } from '@/constants/rarity'

const route = useRoute()
const tripId = route.params.id as string

const detail = ref<any>(null)
const loading = ref(true)
const membersLoading = ref(true)
const actionLoading = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const editForm = ref({ title: '', location: '', rarity: 'common' })
const members = ref<{ user_id: string; display_name: string; resolved: number }[]>([])
const selected = ref<Set<string>>(new Set())
const message = ref('')
const error = ref('')

const rarity = computed(() => rarityOf(detail.value?.trip?.rarity))

const rarityOptions = [
  { key: 'common', zh: '普通', pill: 'bg-gray-100 text-gray-700' },
  { key: 'rare', zh: '稀有', pill: 'bg-blue-100 text-blue-700' },
  { key: 'super_rare', zh: '極稀有', pill: 'bg-amber-100 text-amber-800' },
  { key: 'epic', zh: '史詩', pill: 'bg-purple-100 text-purple-700' },
  { key: 'legendary', zh: '傳說', pill: 'bg-rose-100 text-rose-700' },
]

function startEdit() {
  editForm.value = {
    title: detail.value?.trip?.title || '',
    location: detail.value?.trip?.location || '',
    rarity: detail.value?.trip?.rarity || 'common',
  }
  isEditing.value = true
}

async function saveEdit() {
  if (!editForm.value.title.trim() || saving.value) return
  saving.value = true
  message.value = ''; error.value = ''
  try {
    await api.adminUpdateTrip(tripId, {
      title: editForm.value.title.trim(),
      location: editForm.value.location.trim(),
      rarity: editForm.value.rarity,
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
