import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from './api'

export type Connectivity = 'checking' | 'online' | 'degraded' | 'offline'

export function useHealth() {
  const query = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 5000,
    retry: false
  })

  let connectivity: Connectivity = 'checking'
  if (query.isError) connectivity = 'offline'
  else if (query.data) connectivity = query.data.status === 'ok' ? 'online' : 'degraded'

  return { ...query, connectivity }
}
