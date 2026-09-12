"use client";

import * as React from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { useReducedMotion } from "framer-motion";
import * as THREE from "three";

/** A single slowly rotating wireframe solid — cheap and calm. */
function RotatingSolid() {
  const ref = React.useRef<THREE.Mesh>(null);
  const reduce = useReducedMotion();
  useFrame((state, delta) => {
    if (ref.current && !reduce) {
      ref.current.rotation.x += delta * 0.15;
      ref.current.rotation.y += delta * 0.2;
    }
    if (ref.current) {
      // Gentle parallax toward the pointer.
      ref.current.position.x = THREE.MathUtils.lerp(
        ref.current.position.x,
        state.pointer.x * 0.4,
        0.04
      );
    }
  });
  return (
    <mesh ref={ref}>
      <icosahedronGeometry args={[2.2, 1]} />
      <meshBasicMaterial color="#8b5cf6" wireframe transparent opacity={0.4} />
    </mesh>
  );
}

/** Faint, slow particle drift. */
function Drift({ count = 150 }: { count?: number }) {
  const ref = React.useRef<THREE.Points>(null);
  const reduce = useReducedMotion();
  const positions = React.useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < arr.length; i++) arr[i] = (Math.random() - 0.5) * 12;
    return arr;
  }, [count]);

  useFrame((state) => {
    if (ref.current && !reduce) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.02;
    }
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.04}
        color="#a5b4fc"
        transparent
        opacity={0.5}
        sizeAttenuation
      />
    </points>
  );
}

export default function LoginScene() {
  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [0, 0, 6], fov: 50 }}
      gl={{ antialias: true, alpha: true }}
      style={{ position: "absolute", inset: 0 }}
    >
      <RotatingSolid />
      <Drift />
    </Canvas>
  );
}
