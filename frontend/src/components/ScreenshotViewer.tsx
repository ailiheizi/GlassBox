import { useState } from 'react'
import { Camera, RefreshCw, Download } from 'lucide-react'
import { sandboxApi } from '../api/client'

interface ScreenshotViewerProps {
  userId: string
}

interface ScreenshotData {
  image?: string
  width?: number
  height?: number
  timestamp?: string
}

export function ScreenshotViewer({ userId }: ScreenshotViewerProps) {
  const [screenshot, setScreenshot] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  const captureScreenshot = async () => {
    setLoading(true)
    setError(null)

    try {
      const result = await sandboxApi.getScreenshot(userId)
      if (result.error) {
        setError(result.error)
      } else {
        const data = result.data as ScreenshotData
        setScreenshot(data?.image || null)
        setLastUpdate(new Date())
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  const downloadScreenshot = () => {
    if (!screenshot) return

    const link = document.createElement('a')
    link.href = `data:image/png;base64,${screenshot}`
    link.download = `sandbox-${userId}-${Date.now()}.png`
    link.click()
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Camera className="w-4 h-4" />
          屏幕截图
        </h3>
        <div className="flex gap-2">
          <button
            onClick={captureScreenshot}
            disabled={loading}
            className="px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded text-sm flex items-center gap-1"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? '捕获中...' : '捕获'}
          </button>
          {screenshot && (
            <button
              onClick={downloadScreenshot}
              className="px-3 py-1 bg-gray-600 hover:bg-gray-500 rounded text-sm flex items-center gap-1"
            >
              <Download className="w-4 h-4" />
              下载
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-500 rounded p-3 mb-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {screenshot ? (
        <div className="space-y-2">
          <img
            src={`data:image/png;base64,${screenshot}`}
            alt="Sandbox Screenshot"
            className="w-full rounded border border-gray-700"
          />
          {lastUpdate && (
            <p className="text-xs text-gray-500">
              最后更新: {lastUpdate.toLocaleTimeString()}
            </p>
          )}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <Camera className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p className="text-sm">点击"捕获"按钮获取屏幕截图</p>
        </div>
      )}
    </div>
  )
}