import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useDashboardStore } from '../store/dashboardStore'

export function useMetrics() {
  const { timeRange, setConnections, setTimeseries } = useDashboardStore()

  const health = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 5000,
  })

  const aggregate = useQuery({
    queryKey: ['metrics'],
    queryFn: api.metricsAggregate,
    refetchInterval: 3000,
  })

  const execution = useQuery({
    queryKey: ['execution'],
    queryFn: api.executionCurrent,
    refetchInterval: 2000,
  })

  const safety = useQuery({
    queryKey: ['safety'],
    queryFn: api.safety,
    refetchInterval: 5000,
  })

  const connectionsQuery = useQuery({
    queryKey: ['connections'],
    queryFn: api.connections,
    refetchInterval: 10000,
  })

  const timeseriesQuery = useQuery({
    queryKey: ['timeseries', timeRange],
    queryFn: () => api.metricsTimeseries(timeRange),
    refetchInterval: 10000,
  })

  useEffect(() => {
    if (connectionsQuery.data) setConnections(connectionsQuery.data)
  }, [connectionsQuery.data, setConnections])

  useEffect(() => {
    if (timeseriesQuery.data) setTimeseries(timeseriesQuery.data)
  }, [timeseriesQuery.data, setTimeseries])

  return {
    health: health.data,
    metrics: aggregate.data,
    execution: execution.data,
    safety: safety.data,
    connections: connectionsQuery.data,
    timeseries: timeseriesQuery.data,
    isLoading: health.isLoading || aggregate.isLoading,
  }
}
