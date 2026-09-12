"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";

/**
 * Slide-in drawer with a fading backdrop (used for the mobile sidebar and
 * side panels). Slides from the left by default.
 */
export function Sheet({
  open,
  onClose,
  side = "left",
  className,
  children,
}: {
  open: boolean;
  onClose: () => void;
  side?: "left" | "right";
  className?: string;
  children: React.ReactNode;
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  const x = side === "left" ? "-100%" : "100%";

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <motion.div
            className="absolute inset-0 bg-black/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />
          <motion.div
            className={
              "absolute inset-y-0 " +
              (side === "left" ? "left-0" : "right-0") +
              " w-72 max-w-[85vw] bg-background shadow-popover " +
              (className ?? "")
            }
            initial={{ x }}
            animate={{ x: 0 }}
            exit={{ x }}
            transition={{ type: "spring", stiffness: 360, damping: 34 }}
          >
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
