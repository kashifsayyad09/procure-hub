import { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

const COUNT = 64
const MAX_DIST = 1.9
const MAX_SEGMENTS = 420
const BOX = { x: 5.2, y: 3, z: 1.6 }

function Network({ nodeColor, lineColor }: { nodeColor: string; lineColor: string }) {
  const group = useRef<THREE.Group>(null)
  const points = useRef<THREE.Points>(null)
  const lines = useRef<THREE.LineSegments>(null)

  const { positions, velocities, linePositions } = useMemo(() => {
    const p = new Float32Array(COUNT * 3)
    const v = new Float32Array(COUNT * 3)
    for (let i = 0; i < COUNT; i++) {
      p[i * 3] = (Math.random() * 2 - 1) * BOX.x
      p[i * 3 + 1] = (Math.random() * 2 - 1) * BOX.y
      p[i * 3 + 2] = (Math.random() * 2 - 1) * BOX.z
      v[i * 3] = (Math.random() - 0.5) * 0.25
      v[i * 3 + 1] = (Math.random() - 0.5) * 0.25
      v[i * 3 + 2] = (Math.random() - 0.5) * 0.12
    }
    return { positions: p, velocities: v, linePositions: new Float32Array(MAX_SEGMENTS * 6) }
  }, [])

  useFrame((state, delta) => {
    const dt = Math.min(delta, 0.05)
    const lim = [BOX.x, BOX.y, BOX.z]
    for (let i = 0; i < COUNT * 3; i++) {
      positions[i] += velocities[i] * dt
      if (Math.abs(positions[i]) > lim[i % 3]) velocities[i] *= -1
    }
    let seg = 0
    for (let i = 0; i < COUNT && seg < MAX_SEGMENTS; i++) {
      for (let j = i + 1; j < COUNT && seg < MAX_SEGMENTS; j++) {
        const dx = positions[i * 3] - positions[j * 3]
        const dy = positions[i * 3 + 1] - positions[j * 3 + 1]
        const dz = positions[i * 3 + 2] - positions[j * 3 + 2]
        if (dx * dx + dy * dy + dz * dz < MAX_DIST * MAX_DIST) {
          linePositions.set([positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2], positions[j * 3], positions[j * 3 + 1], positions[j * 3 + 2]], seg * 6)
          seg++
        }
      }
    }
    if (points.current) points.current.geometry.attributes.position.needsUpdate = true
    if (lines.current) {
      lines.current.geometry.attributes.position.needsUpdate = true
      lines.current.geometry.setDrawRange(0, seg * 2)
    }
    if (group.current) {
      // gentle mouse parallax
      group.current.rotation.y += (state.pointer.x * 0.25 - group.current.rotation.y) * 0.04
      group.current.rotation.x += (-state.pointer.y * 0.15 - group.current.rotation.x) * 0.04
    }
  })

  return (
    <group ref={group}>
      <points ref={points}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} usage={THREE.DynamicDrawUsage} />
        </bufferGeometry>
        <pointsMaterial color={nodeColor} size={0.09} sizeAttenuation />
      </points>
      <lineSegments ref={lines}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[linePositions, 3]} usage={THREE.DynamicDrawUsage} />
        </bufferGeometry>
        <lineBasicMaterial color={lineColor} transparent opacity={0.28} />
      </lineSegments>
    </group>
  )
}

/** Stops rendering while the tab is hidden so the GPU is idle in the background. */
export default function ParticleNetwork({ nodeColor, lineColor }: { nodeColor: string; lineColor: string }) {
  const [visible, setVisible] = useState(() => !document.hidden)
  useEffect(() => {
    const onVis = () => setVisible(!document.hidden)
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])
  return (
    <Canvas camera={{ position: [0, 0, 6.5], fov: 55 }} dpr={[1, 1.5]} frameloop={visible ? 'always' : 'never'} gl={{ antialias: false, powerPreference: 'low-power' }}>
      <Network nodeColor={nodeColor} lineColor={lineColor} />
    </Canvas>
  )
}
