"use client";

/**
 * Copy a section's text to the clipboard.
 *
 * Researchers move findings into notes and drafts, so the sections worth
 * quoting get one of these. It reports failure rather than showing a false
 * "Copied" - the Clipboard API is unavailable over plain HTTP and can be
 * refused by permissions policy, and a lie here costs someone their quote.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { IconCheck, IconCopy } from "@/components/Icons";

type Result = "idle" | "copied" | "failed";

export default function CopyButton({
  text,
  label = "Copy",
}: {
  text: string;
  label?: string;
}) {
  const [result, setResult] = useState<Result>("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const copy = useCallback(async () => {
    try {
      if (!navigator.clipboard) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(text);
      setResult("copied");
    } catch {
      setResult("failed");
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setResult("idle"), 2000);
  }, [text]);

  if (!text) return null;

  return (
    <button
      className="btn btn--sm btn--ghost"
      onClick={() => void copy()}
      aria-live="polite"
    >
      {result === "copied" ? <IconCheck size={14} /> : <IconCopy size={14} />}
      {result === "copied" ? "Copied" : result === "failed" ? "Copy failed" : label}
    </button>
  );
}
