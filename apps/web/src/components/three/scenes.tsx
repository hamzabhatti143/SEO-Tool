"use client";

import * as React from "react";
import dynamic from "next/dynamic";

import { isWebGLAvailable } from "@/lib/webgl";
import { ThreeErrorBoundary } from "./three-error-boundary";

// Lazy-load the Three.js bundles client-side only (ssr:false) so they never
// block initial page load / first paint. `loading` renders nothing — the
// page's static gradient shows through until (and unless) the scene mounts.
const HeroScene = dynamic(() => import("./hero-scene"), {
  ssr: false,
  loading: () => null,
});
const LoginScene = dynamic(() => import("./login-scene"), {
  ssr: false,
  loading: () => null,
});

/** Mounts a scene only when WebGL is available; degrades to nothing (the
 *  static gradient behind it) if unsupported or if the scene throws. */
function GuardedScene({ Scene }: { Scene: React.ComponentType }) {
  const [webglOk, setWebglOk] = React.useState(false);

  React.useEffect(() => {
    setWebglOk(isWebGLAvailable());
  }, []);

  if (!webglOk) return null;

  return (
    <div className="absolute inset-0" aria-hidden="true">
      <ThreeErrorBoundary>
        <Scene />
      </ThreeErrorBoundary>
    </div>
  );
}

export function HeroCanvas() {
  return <GuardedScene Scene={HeroScene} />;
}

export function LoginCanvas() {
  return <GuardedScene Scene={LoginScene} />;
}
