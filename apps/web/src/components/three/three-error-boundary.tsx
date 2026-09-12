"use client";

import * as React from "react";

/**
 * Catches any error thrown while rendering a Three.js scene (WebGL context
 * loss, shader failure, etc.) and renders `fallback` (usually nothing — the
 * static gradient sits behind the canvas) instead of crashing the page.
 */
export class ThreeErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    // Non-fatal: the page degrades to its static background.
    console.warn("3D scene failed to render, falling back:", error);
  }

  render() {
    if (this.state.hasError) return this.props.fallback ?? null;
    return this.props.children;
  }
}
