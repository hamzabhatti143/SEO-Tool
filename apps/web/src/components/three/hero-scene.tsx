"use client";

import * as React from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import { useReducedMotion } from "framer-motion";
import * as THREE from "three";

const INDIGO = new THREE.Color("#6366f1");
const VIOLET = new THREE.Color("#8b5cf6");

/** Ascending bars — an abstract "SEO growth" chart that gently breathes. */
function GrowthBars() {
  const group = React.useRef<THREE.Group>(null);
  const reduce = useReducedMotion();
  const heights = React.useMemo(
    () => [0.7, 1.05, 1.35, 1.15, 1.8, 2.15, 2.6],
    []
  );

  useFrame((state) => {
    const g = group.current;
    if (!g) return;
    const t = reduce ? 0 : state.clock.elapsedTime;
    g.children.forEach((child, i) => {
      const mesh = child as THREE.Mesh;
      const h = heights[i] + Math.sin(t * 1.4 + i * 0.6) * 0.12;
      mesh.scale.y = h;
      mesh.position.y = h / 2 - 1.6;
    });
  });

  return (
    <group ref={group}>
      {heights.map((_, i) => {
        const color = INDIGO.clone().lerp(VIOLET, i / (heights.length - 1));
        return (
          <mesh key={i} position={[(i - 3) * 0.72, 0, 0]}>
            <boxGeometry args={[0.46, 1, 0.46]} />
            <meshStandardMaterial
              color={color}
              emissive={color}
              emissiveIntensity={0.45}
              metalness={0.35}
              roughness={0.35}
            />
          </mesh>
        );
      })}
    </group>
  );
}

/** A few floating geometric accents around the chart. */
function FloatingShapes() {
  return (
    <>
      <Float speed={2} rotationIntensity={1.2} floatIntensity={1.4}>
        <mesh position={[-3.2, 1.6, -1]}>
          <icosahedronGeometry args={[0.55, 0]} />
          <meshStandardMaterial
            color={VIOLET}
            emissive={VIOLET}
            emissiveIntensity={0.35}
            roughness={0.3}
            metalness={0.4}
          />
        </mesh>
      </Float>
      <Float speed={1.6} rotationIntensity={1.5} floatIntensity={1.2}>
        <mesh position={[3.4, 2, -1.5]}>
          <torusGeometry args={[0.42, 0.16, 16, 40]} />
          <meshStandardMaterial
            color={INDIGO}
            emissive={INDIGO}
            emissiveIntensity={0.35}
            roughness={0.3}
            metalness={0.4}
          />
        </mesh>
      </Float>
      <Float speed={2.4} rotationIntensity={1} floatIntensity={1.6}>
        <mesh position={[2.6, -1.4, 0.5]}>
          <octahedronGeometry args={[0.4, 0]} />
          <meshStandardMaterial
            color="#a5b4fc"
            emissive="#a5b4fc"
            emissiveIntensity={0.3}
            roughness={0.3}
          />
        </mesh>
      </Float>
    </>
  );
}

/** Subtle drifting particle field. */
function Particles({ count = 350 }: { count?: number }) {
  const ref = React.useRef<THREE.Points>(null);
  const reduce = useReducedMotion();
  const positions = React.useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < arr.length; i++) arr[i] = (Math.random() - 0.5) * 16;
    return arr;
  }, [count]);

  useFrame((state) => {
    if (ref.current && !reduce) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.03;
    }
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.035}
        color="#c7d2fe"
        transparent
        opacity={0.6}
        sizeAttenuation
      />
    </points>
  );
}

/** Tilts the whole scene subtly toward the pointer. */
function PointerRig({ children }: { children: React.ReactNode }) {
  const ref = React.useRef<THREE.Group>(null);
  const reduce = useReducedMotion();
  useFrame((state) => {
    const g = ref.current;
    if (!g || reduce) return;
    g.rotation.y = THREE.MathUtils.lerp(g.rotation.y, state.pointer.x * 0.35, 0.05);
    g.rotation.x = THREE.MathUtils.lerp(g.rotation.x, -state.pointer.y * 0.2, 0.05);
  });
  return <group ref={ref}>{children}</group>;
}

export default function HeroScene() {
  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [0, 0.5, 7], fov: 50 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ position: "absolute", inset: 0 }}
    >
      <ambientLight intensity={0.9} />
      <directionalLight position={[4, 6, 5]} intensity={1.6} />
      <pointLight position={[-5, -2, 3]} intensity={30} color="#6366f1" />
      <PointerRig>
        <GrowthBars />
        <FloatingShapes />
        <Particles />
      </PointerRig>
    </Canvas>
  );
}
