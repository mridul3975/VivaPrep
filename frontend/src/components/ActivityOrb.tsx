import { ThinkingOrb, type OrbState, type OrbSize } from 'thinking-orbs'

export default function ActivityOrb({
  state,
  size = 20,
  active = true,
}: {
  state: OrbState
  size?: OrbSize
  active?: boolean
}) {
  return (
    <ThinkingOrb
      state={state}
      size={size}
      theme="dark"
      color="#dedee3"
      paused={!active}
      aria-hidden="true"
      data-orb-state={state}
      data-orb-active={active}
      className="activity-orb"
    />
  )
}
