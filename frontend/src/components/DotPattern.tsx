import { useEffect, useRef } from 'react'

/** Shared page decoration; pointer updates stay outside React's render cycle. */
export default function DotPattern() {
  const backdrop = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const node = backdrop.current
    if (!node) return
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)')
    let active = false

    const hide = () => {
      active = false
      node.dataset.pointerActive = 'false'
      node.dataset.pointerMoving = 'false'
    }
    const move = (event: PointerEvent) => {
      if (event.pointerType === 'touch' || !finePointer.matches) {
        hide()
        return
      }
      // The first position snaps into place; subsequent moves ease after it.
      node.dataset.pointerMoving = active ? 'true' : 'false'
      node.style.setProperty('--dot-pointer-x', `${event.clientX}px`)
      node.style.setProperty('--dot-pointer-y', `${event.clientY}px`)
      node.dataset.pointerActive = 'true'
      active = true
    }
    const leave = (event: PointerEvent) => {
      if (event.relatedTarget === null) hide()
    }
    const visibility = () => {
      node.dataset.visible = String(!document.hidden)
      if (document.hidden) hide()
    }

    visibility()
    window.addEventListener('pointermove', move, { passive: true })
    window.addEventListener('pointerout', leave, { passive: true })
    window.addEventListener('blur', hide)
    document.addEventListener('visibilitychange', visibility)
    finePointer.addEventListener('change', hide)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerout', leave)
      window.removeEventListener('blur', hide)
      document.removeEventListener('visibilitychange', visibility)
      finePointer.removeEventListener('change', hide)
      hide()
    }
  }, [])

  return (
    <div className="dot-pattern" ref={backdrop} aria-hidden="true">
      <div className="dot-pattern-wave" />
      <div className="dot-pattern-cursor" />
    </div>
  )
}
