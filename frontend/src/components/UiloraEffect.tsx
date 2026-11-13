import { useEffect, useRef, useState } from 'react'
import { auroraShader, rasterShader, vertexShader } from './uilora-shaders'
import './uilora-effects.css'

/** Uilora's silver folds and pointer-reactive raster, with bounded rendering. */
export default function UiloraEffect({ variant }: { variant: 'aurora' | 'raster' }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [generation, restart] = useState(0)
  useEffect(() => {
    const node = canvas.current
    if (!node) return
    const gl = node.getContext('webgl', { alpha: true, premultipliedAlpha: false, antialias: false, powerPreference: 'low-power' })
    if (!gl) return
    const shaders: WebGLShader[] = []
    let program: WebGLProgram | null = null
    let buffer: WebGLBuffer | null = null
    try {
      program = gl.createProgram()
      if (!program) return
      for (const [type, text] of [[gl.VERTEX_SHADER, vertexShader], [gl.FRAGMENT_SHADER, variant === 'raster' ? rasterShader : auroraShader]] as const) {
        const shader = gl.createShader(type)
        if (!shader) throw new Error('Shader unavailable')
        shaders.push(shader); gl.shaderSource(shader, text); gl.compileShader(shader)
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error('Shader unsupported')
        gl.attachShader(program, shader)
      }
      gl.linkProgram(program)
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Effect unsupported')
      gl.useProgram(program)
      buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 0, 0, 3, -1, 2, 0, -1, 3, 0, 2]), gl.STATIC_DRAW)
      for (const [name, offset] of [['position', 0], ['uv', 8]] as const) {
        const attribute = gl.getAttribLocation(program, name)
        gl.enableVertexAttribArray(attribute); gl.vertexAttribPointer(attribute, 2, gl.FLOAT, false, 16, offset)
      }
    } catch {
      shaders.forEach(shader => gl.deleteShader(shader)); gl.deleteProgram(program); gl.deleteBuffer(buffer)
      return
    }
    const uniform = (name: string) => gl.getUniformLocation(program!, name)
    const timeUniform = uniform('uTime'), resolutionUniform = uniform('uResolution'), mouseUniform = uniform('uMouse')
    gl.uniform1f(uniform('uSpeed'), variant === 'raster' ? .65 : .6)
    if (variant === 'raster') {
      gl.uniform3f(uniform('uColor'), .14, .145, .16)
      gl.uniform3f(uniform('uAccentColor'), .30, .31, .33)
      gl.uniform1f(uniform('uDensity'), 38)
    } else {
      gl.uniform3f(uniform('uBaseColor'), .04, .04, .045)
      gl.uniform3f(uniform('uWaveColor'), .82, .82, .84)
      gl.uniform1f(uniform('uIntensity'), .65)
    }
    const reduced = matchMedia('(prefers-reduced-motion: reduce)')
    let visible = true, frame = 0, last = -100, elapsed = 0
    let mouseX = -2, mouseY = -2, pointerChanged = false
    const draw = (now: number) => {
      frame = 0
      if (document.hidden || !visible || gl.isContextLost()) return
      // Pointer updates bypass the idle 30 fps throttle; no easing tail.
      if (pointerChanged || now - last >= 33 || reduced.matches) {
        if (!reduced.matches) elapsed += Math.min(100, Math.max(0, now - last)) / 1000
        last = now
        pointerChanged = false
        gl.uniform1f(timeUniform, reduced.matches ? 0 : elapsed)
        gl.uniform2f(mouseUniform, reduced.matches ? -2 : mouseX, reduced.matches ? -2 : mouseY)
        gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT)
        gl.drawArrays(gl.TRIANGLES, 0, 3)
        node.dataset.rendered = 'true'
      }
      if (!reduced.matches) frame = requestAnimationFrame(draw)
    }
    const schedule = () => { cancelAnimationFrame(frame); last = -100; frame = requestAnimationFrame(draw) }
    const resize = () => {
      const rect = node.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 1.5)
      node.width = Math.max(1, Math.round(rect.width * dpr)); node.height = Math.max(1, Math.round(rect.height * dpr))
      gl.viewport(0, 0, node.width, node.height); gl.uniform2f(resolutionUniform, node.width, node.height); schedule()
    }
    const move = (event: PointerEvent) => {
      if (event.pointerType === 'touch' || reduced.matches) return
      const rect = node.getBoundingClientRect()
      mouseX = (event.clientX - rect.left) / Math.max(1, rect.width)
      mouseY = 1 - (event.clientY - rect.top) / Math.max(1, rect.height)
      pointerChanged = true
    }
    const leave = () => { mouseX = -2; mouseY = -2; pointerChanged = true }
    const lost = (event: Event) => { event.preventDefault(); cancelAnimationFrame(frame); delete node.dataset.rendered }
    const restored = () => restart(value => value + 1)
    const observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; schedule() })
    const sizing = new ResizeObserver(resize)
    observer.observe(node); sizing.observe(node); resize()
    window.addEventListener('pointermove', move, { passive: true }); window.addEventListener('blur', leave)
    document.addEventListener('pointerleave', leave); document.addEventListener('visibilitychange', schedule)
    reduced.addEventListener('change', schedule)
    node.addEventListener('webglcontextlost', lost); node.addEventListener('webglcontextrestored', restored)
    return () => {
      cancelAnimationFrame(frame); observer.disconnect(); sizing.disconnect()
      window.removeEventListener('pointermove', move); window.removeEventListener('blur', leave)
      document.removeEventListener('pointerleave', leave); document.removeEventListener('visibilitychange', schedule)
      reduced.removeEventListener('change', schedule)
      node.removeEventListener('webglcontextlost', lost); node.removeEventListener('webglcontextrestored', restored)
      shaders.forEach(shader => gl.deleteShader(shader)); gl.deleteBuffer(buffer); gl.deleteProgram(program)
    }
  }, [variant, generation])
  return <canvas ref={canvas} className={`uilora-effect uilora-${variant}`} aria-hidden="true" />
}
