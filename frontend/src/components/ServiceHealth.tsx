import { useCallback } from 'react'
import { useStore } from '../store'
import { checkServiceHealth } from '../api/client'
import { usePolling } from '../hooks/useSSE'
import { Activity, CheckCircle, XCircle, Clock } from 'lucide-react'

export function ServiceHealth() {
  const { services, updateService } = useStore()

  const checkAllServices = useCallback(async () => {
    const serviceNames = ['gateway', 'auth', 'memory', 'index', 'browser', 'task', 'ai'] as const

    for (const name of serviceNames) {
      try {
        const result = await checkServiceHealth(name)
        updateService(name, {
          status: result.status === 200 ? 'healthy' : 'unhealthy',
          latency: result.latency,
        })
      } catch {
        updateService(name, { status: 'unhealthy' })
      }
    }
  }, [updateService])

  usePolling(checkAllServices, 5000)

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'unhealthy':
        return <XCircle className="w-5 h-5 text-red-500" />
      default:
        return <Clock className="w-5 h-5 text-yellow-500 animate-pulse" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'border-green-500/30 bg-green-500/10'
      case 'unhealthy':
        return 'border-red-500/30 bg-red-500/10'
      default:
        return 'border-yellow-500/30 bg-yellow-500/10'
    }
  }

  return (
    <div className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5" />
        <h2 className="text-lg font-semibold">服务健康状态</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {services.map((service) => (
          <div
            key={service.name}
            className={`p-4 rounded-lg border ${getStatusColor(service.status)}`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium capitalize">{service.name}</span>
              {getStatusIcon(service.status)}
            </div>
            <div className="text-sm text-gray-400">
              <div>{service.url}</div>
              {service.latency !== undefined && (
                <div className="mt-1">
                  延迟: <span className="text-white">{service.latency}ms</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
