import { useAccessibility } from '../accessibility-context'

type SubtitleOverlayProps = {
  subtitle: string
}

export function SubtitleOverlay({ subtitle }: SubtitleOverlayProps) {
  const { settings } = useAccessibility()
  const positionStyle = settings.subtitlePosition === 'Top' ? { top: '10%' } : { bottom: '12%' }
  const background =
    settings.subtitleBackground === 'Solid'
      ? 'rgba(8,12,28,0.92)'
      : settings.subtitleBackground === 'Semi Transparent'
        ? 'rgba(8,12,28,0.6)'
        : 'transparent'

  return (
    <div className="subtitle-overlay" style={positionStyle}>
      <span
        style={{
          fontSize: `${settings.subtitleSize}px`,
          maxWidth: `${settings.subtitleWidth}vw`,
          borderRadius: `${settings.subtitleRadius}px`,
          background,
        }}
      >
        {subtitle}
      </span>
    </div>
  )
}
