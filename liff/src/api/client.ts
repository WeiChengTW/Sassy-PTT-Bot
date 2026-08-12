const API_BASE = '/liff'

let _userId = ''
let _groupId = ''
let _idToken = ''

export function setLiffContext(userId: string, groupId: string, idToken = '') {
  _userId = userId
  _groupId = groupId
  _idToken = idToken
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-LIFF-UserId': _userId,
    'X-LIFF-GroupId': _groupId,
    ...(_idToken ? { Authorization: `Bearer ${_idToken}` } : {}),
    ...((opts.headers as Record<string, string>) || {}),
  }
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers })
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  me: () => req<{ user_id: string; role: string; group_id: string }>('/me'),
  dashboard: (days = 30) => req<any>(`/dashboard?days=${days}`),
  trips: () => req<any[]>('/trips'),
  tripDetail: (id: string) => req<any>(`/trips/${id}`),
  badges: (userId: string) => req<any[]>(`/badges/${userId}`),
  adminCreateTrip: (body: any) => req<any>('/admin/trips', { method: 'POST', body: JSON.stringify(body) }),
  adminAddParticipants: (tripId: string, userIds: string[]) =>
    req<any>(`/admin/trips/${tripId}/participants`, { method: 'POST', body: JSON.stringify({ user_ids: userIds }) }),
  adminEndTrip: (tripId: string) => req<any>(`/admin/trips/${tripId}/end`, { method: 'POST' }),
  adminAwardBadges: (tripId: string) => req<any>(`/admin/trips/${tripId}/award-badges`, { method: 'POST' }),
  leaderboard: () => req<any>('/leaderboard'),
  interactions: () => req<any>('/interactions'),
  topics: () => req<any>('/topics'),
  profile: (userId: string) => req<any>(`/profile/${userId}`),
}