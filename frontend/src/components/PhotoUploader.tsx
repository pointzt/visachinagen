'use client'

import { DragEvent, useRef, useState } from 'react'
import { CameraIcon, UploadIcon } from 'lucide-react'
import { useWebcam } from '@/hooks/useWebcam'
import { cn } from '@/lib/utils'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

interface PhotoUploaderProps {
  onFileSelect: (file: File) => void
  previewUrl: string | null
  error: string | null
  onClear: () => void
}

export default function PhotoUploader({ onFileSelect, previewUrl, error, onClear }: PhotoUploaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [showWebcam, setShowWebcam] = useState(false)
  const { videoRef, active: camActive, error: camError, start, stop, capture } = useWebcam()

  function handleFiles(files: FileList | null) {
    if (files && files[0]) onFileSelect(files[0])
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  function handleCaptureAndStop() {
    const file = capture()
    if (file) {
      onFileSelect(file)
      stop()
      setShowWebcam(false)
    }
  }

  function openWebcam() {
    setShowWebcam(true)
    start()
  }

  function closeWebcam() {
    stop()
    setShowWebcam(false)
  }

  if (showWebcam) {
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="relative aspect-video overflow-hidden rounded-lg bg-black">
          <video ref={videoRef} className="w-full h-full object-cover" muted playsInline />
          {!camActive && (
            <div className="absolute inset-0 flex items-center justify-center text-white/70 text-sm">
              {camError || 'Starting camera...'}
            </div>
          )}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-28 h-36 sm:w-40 sm:h-52 rounded-full border-2 border-white/40" />
          </div>
        </div>
        <div className="flex gap-3">
          <Button onClick={handleCaptureAndStop} disabled={!camActive} className="flex-1">
            Take Photo
          </Button>
          <Button variant="outline" onClick={closeWebcam}>
            Cancel
          </Button>
        </div>
        <p className="text-center text-xs text-muted-foreground">Position your face inside the oval</p>
      </div>
    )
  }

  if (previewUrl) {
    return (
      <div className="space-y-3 animate-fade-in">
        <div className="relative mx-auto aspect-square max-w-48 overflow-hidden rounded-lg border">
          <img src={previewUrl} alt="Uploaded" className="h-full w-full object-cover" />
        </div>
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={onClear}>
            Choose another photo
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          'cursor-pointer rounded-lg border border-dashed p-6 text-center transition-colors',
          dragging ? 'border-ring bg-accent' : 'hover:bg-accent/50'
        )}
      >
        <div className="flex flex-col items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-muted">
            <UploadIcon className="size-5" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium">Drop your photo here</p>
            <p className="text-sm text-muted-foreground">or click to browse · up to 15 MB</p>
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      <Button variant="outline" onClick={openWebcam} className="w-full">
        <CameraIcon />
        Use camera
      </Button>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  )
}
