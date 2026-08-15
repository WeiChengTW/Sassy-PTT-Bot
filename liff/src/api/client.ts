const API_BASE = '/liff'

export interface BoardRow {
  user_id: string
  name: string
  value: number
  value_str: string
  detail?: string | null
  ongoing?: boolean
  breakdown?: Record<string, number>   // score variant
  axes?: Record<string, number>        // radar variant
}
export interface BoardHighlight {
  label: string
  name: string
  value_str: string
  note?: string | null
}
export interface Board {
  id: string
  title: string
  emoji: string
  unit: string
  subtitle: string
  variant: 'rank' | 'score' | 'radar'
  accent: string
  sparse: boolean
  rows: BoardRow[]
  highlight: BoardHighlight | null
}

let _userId = ''
let _groupId = ''
let _idToken = ''
let _adminGroup = localStorage.getItem('adminGroup') || ''
let _period = localStorage.getItem('period') || 'all'

export function setLiffContext(userId: string, groupId: string, idToken = '') {
  _userId = userId
  _groupId = groupId
  _idToken = idToken
}

export function setAdminGroup(groupId: string) {
  _adminGroup = groupId
  localStorage.setItem('adminGroup', groupId)
}
export function getAdminGroup() { return _adminGroup }

export function setPeriod(period: string) {
  _period = period
  localStorage.setItem('period', period)
}
export function getPeriod() { return _period }

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-LIFF-UserId': _userId,
    'X-LIFF-GroupId': _groupId,
    ...(_idToken ? { Authorization: `Bearer ${_idToken}` } : {}),
    ...((opts.headers as Record<string, string>) || {}),
  }
  // Merge existing query with injected params
  const [base, existing] = path.split('?')
  const qs = new URLSearchParams(existing || '')
  if (_adminGroup) qs.set('g', _adminGroup)
  if (_period && _period !== 'all') qs.set('period', _period)
  const query = qs.toString()
  const fullPath = query ? `${base}?${query}` : base
  const res = await fetch(`${API_BASE}${fullPath}`, { ...opts, headers })
  if (!res.ok) {
    let reason = ''
    try { const j = await res.json(); reason = j.reason || j.error || '' } catch {}
    throw new Error(reason ? `${res.status}: ${reason}` : `API error ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  me: () => req<{ user_id: string; role: string; group_id: string }>('/me'),
  dashboard: (days = 30) => req<any>(`/dashboard?days=${days}`),
  trips: () => req<any[]>('/trips'),
  tripDetail: (id: string) => req<any>(`/trips/${id}`),
  badges: (userId: string) => req<any[]>(`/badges/${userId}`),
  adminCreateTrip: (body: any) => req<any>('/admin/trips', { method: 'POST', body: JSON.stringify(body) }),
  adminUpdateTrip: (tripId: string, body: { title?: string; location?: string; rarity?: string; types?: string[]; custom_emoji?: string; start_date?: number | null; end_date?: number | null }) =>
    req<any>(`/admin/trips/${tripId}/update`, { method: 'POST', body: JSON.stringify(body) }),
  adminUpdateTripTitle: (tripId: string, title: string) =>
    req<any>(`/admin/trips/${tripId}/title`, { method: 'POST', body: JSON.stringify({ title }) }),
  adminAddParticipants: (tripId: string, userIds: string[]) =>
    req<any>(`/admin/trips/${tripId}/participants`, { method: 'POST', body: JSON.stringify({ user_ids: userIds }) }),
  adminEndTrip: (tripId: string) => req<any>(`/admin/trips/${tripId}/end`, { method: 'POST' }),
  adminAwardBadges: (tripId: string) => req<any>(`/admin/trips/${tripId}/award-badges`, { method: 'POST' }),
  leaderboard: () => req<any>('/leaderboard'),
  leaderboards: () => req<{ boards: Board[] }>('/leaderboards'),
  interactions: () => req<any>('/interactions'),
  topics: () => req<any>('/topics'),
  profile: (userId: string) => req<any>(`/profile/${userId}`),
  pulse: () => req<any>('/pulse'),
  compare: (a: string, b: string) => req<any>(`/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  adminAnalyzeTopics: () => req<{ updated: number; success: boolean }>('/admin/analyze-topics', { method: 'POST' }),
  adminGroups: () => req<any[]>('/admin/groups'),
  adminMembers: () => req<{ user_id: string; display_name: string; source: string; resolved: number }[]>('/admin/members'),
  periods: () => req<{ years: string[]; months: string[] }>('/periods'),
}