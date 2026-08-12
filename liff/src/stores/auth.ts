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

      // Try to get groupId from LIFF context
      const ctx = liff.getContext()
      this.groupId = (ctx as any)?.groupId || ''

      const idToken = liff.getIDToken() ?? ''
      setLiffContext(this.userId, this.groupId, idToken)

      const me = await api.me()
      this.role = me.role as 'admin' | 'member'
      this.isMember = true
      this.initialized = true
    },
  },
})