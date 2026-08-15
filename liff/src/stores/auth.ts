import { defineStore } from 'pinia'
import liff from '@line/liff'
import { api, setLiffContext } from '@/api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    initialized: false,
    userId: '',
    role: '' as 'admin' | 'member' | '',
    groupId: '',
    isMember: false,
  }),
  actions: {
    async init() {
      if (this.initialized) return
      await liff.init({ liffId: import.meta.env.VITE_LIFF_ID as string })
      if (!liff.isLoggedIn()) {
        liff.login()
        return
      }
      const profile = await liff.getProfile()
      this.userId = profile.userId

      // Try to get groupId from LIFF context. getContext() only returns a real
      // groupId (C + 32 hex) when opened inside a group chat; in 1:1 / rich-menu
      // (utou) contexts it exposes a utouId (UUID) instead — never send that as a
      // group. The backend falls back to the user's own group when this is empty.
      const ctx = liff.getContext()
      const rawGroup = (ctx as any)?.groupId || ''
      this.groupId = /^C[0-9a-f]{32}$/i.test(rawGroup) ? rawGroup : ''

      const idToken = liff.getIDToken() ?? ''
      setLiffContext(this.userId, this.groupId, idToken)

      const me = await api.me()
      this.role = me.role as 'admin' | 'member'
      this.isMember = true
      this.initialized = true
    },
  },
})