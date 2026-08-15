import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('@/views/DashboardView.vue'), meta: { requiresParticipant: true } },
    { path: '/trips', component: () => import('@/views/TripListView.vue'), meta: { requiresParticipant: true } },
    { path: '/timeline', component: () => import('@/views/TimelineView.vue'), meta: { requiresParticipant: true } },
    { path: '/trips/:id', component: () => import('@/views/TripDetailView.vue'), meta: { requiresParticipant: true } },
    { path: '/badges', component: () => import('@/views/BadgesView.vue'), meta: { requiresParticipant: true } },
    { path: '/admin', component: () => import('@/views/TripAdminListView.vue'), meta: { requiresAdmin: true } },
    { path: '/admin/trips/new', component: () => import('@/views/TripCreateView.vue'), meta: { requiresAdmin: true } },
    { path: '/admin/trips/:id', component: () => import('@/views/TripManageView.vue'), meta: { requiresAdmin: true } },
    { path: '/leaderboard', component: () => import('@/views/LeaderboardView.vue'), meta: { requiresParticipant: true } },
    { path: '/interactions', component: () => import('@/views/InteractionView.vue'), meta: { requiresParticipant: true } },
    { path: '/topics', component: () => import('@/views/TopicsView.vue'), meta: { requiresParticipant: true } },
    { path: '/profile', component: () => import('@/views/ProfileView.vue'), meta: { requiresParticipant: true } },
    { path: '/403', component: () => import('@/views/ForbiddenView.vue') },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.initialized) {
    try { await auth.init() } catch { return '/403' }
  }
  if (to.meta.requiresAdmin && auth.role !== 'admin') return '/'
  if (to.meta.requiresParticipant && !auth.isMember) return '/403'
})

export default router