'use client'

import { motion, type HTMLMotionProps } from 'framer-motion'
import { forwardRef } from 'react'

// Fade in from below — for page content
export const FadeIn = forwardRef<
  HTMLDivElement,
  HTMLMotionProps<'div'> & { delay?: number }
>(({ delay = 0, children, ...props }, ref) => (
  <motion.div
    ref={ref}
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.3, delay, ease: 'easeOut' }}
    {...props}
  >
    {children}
  </motion.div>
))

FadeIn.displayName = 'FadeIn'

// Stagger container — wraps children that should animate in sequence
export function StaggerContainer({
  children,
  className,
  stagger = 0.05,
}: {
  children: React.ReactNode
  className?: string
  stagger?: number
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: {
          transition: {
            staggerChildren: stagger,
          },
        },
      }}
    >
      {children}
    </motion.div>
  )
}

// Stagger item — use inside StaggerContainer
export const StaggerItem = forwardRef<HTMLDivElement, HTMLMotionProps<'div'>>(
  ({ children, ...props }, ref) => (
    <motion.div
      ref={ref}
      variants={{
        hidden: { opacity: 0, y: 8 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
      }}
      {...props}
    >
      {children}
    </motion.div>
  )
)

StaggerItem.displayName = 'StaggerItem'

// Scale in — for modals and popups
export const ScaleIn = forwardRef<
  HTMLDivElement,
  HTMLMotionProps<'div'>
>(({ children, ...props }, ref) => (
  <motion.div
    ref={ref}
    initial={{ opacity: 0, scale: 0.95 }}
    animate={{ opacity: 1, scale: 1 }}
    exit={{ opacity: 0, scale: 0.95 }}
    transition={{ duration: 0.2, ease: 'easeOut' }}
    {...props}
  >
    {children}
  </motion.div>
))

ScaleIn.displayName = 'ScaleIn'
