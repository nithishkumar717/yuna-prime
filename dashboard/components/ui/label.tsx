/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║                                                                  ║
 * ║   ░█▄░█░█▀▀░█▀▄░█▀▄   ░█░█   ░█░░░▀█▀░█░█░█▀▀                 ║
 * ║   ░█░▀█░█▀▀░█▀▄░█░█   ░▄▀▄   ░█░░░░█░░▀▄▀░█▀▀                 ║
 * ║   ░▀░░▀░▀▀▀░▀░▀░▀▀░   ░▀░▀   ░▀▀▀░▀█▀░░▀░░▀▀▀                 ║
 * ║                                                                  ║
 * ║           © 2026 Nerd X Live — All Rights Reserved              ║
 * ║                                                                  ║
 * ║   discord  ──  https://discord.gg/YzHCx5yQXv                    ║
 * ║   github   ──  https://github.com/nithishkumar717/yuna-bot      ║
 * ║                                                                  ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

import * as React from "react"
import { cn } from "@/lib/utils"

const Label = React.forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn(
      "text-sm font-bold leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-slate-300",
      className
    )}
    {...props}
  />
))
Label.displayName = "Label"

export { Label }
