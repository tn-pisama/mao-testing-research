import { toPng, toSvg } from 'html-to-image'

export interface ExportOptions {
  filename?: string
  format?: 'png' | 'svg'
  scale?: number // 1-4 for resolution
  backgroundColor?: string
}

export async function exportReactFlowAsImage(
  element: HTMLElement,
  options: ExportOptions = {}
): Promise<void> {
  const {
    filename = 'workflow-diagram',
    format = 'png',
    scale = 2,
    backgroundColor = '#0f172a', // slate-950
  } = options

  const exportFn = format === 'png' ? toPng : toSvg

  try {
    const dataUrl = await exportFn(element, {
      pixelRatio: scale,
      backgroundColor,
      cacheBust: true,
    })

    // Download file
    const link = document.createElement('a')
    link.download = `${filename}.${format}`
    link.href = dataUrl
    link.click()
  } catch (err) {
    console.error('Export failed:', err)
    throw new Error('Failed to export diagram')
  }
}
