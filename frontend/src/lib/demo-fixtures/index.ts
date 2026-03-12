import type { Trace, State, Detection, HealingRecord } from '../api'

// Re-export existing types for convenience
export type DemoTrace = Trace & { states: DemoState[] }
export type DemoDetection = Detection
export type DemoHealingRecord = HealingRecord

export interface DemoState extends State {
  trace_id: string
  step_index: number
  action: string
  input_data: Record<string, unknown>
  output_data: Record<string, unknown>
}

export interface DemoScenario {
  id: string
  title: string
  description: string
  icon: string
  framework: string

  traces: DemoTrace[]
  detections: DemoDetection[]
  healingRecords: DemoHealingRecord[]

  highlights: {
    traceId: string
    detectionId: string | null
    healingId: string | null
    explanation: string
  }
}

export { loopScenario } from './scenario-loop'
export { corruptionScenario } from './scenario-corruption'
export { hallucinationScenario } from './scenario-hallucination'
export { healthyScenario } from './scenario-healthy'
export { injectionScenario } from './scenario-injection'

import { loopScenario } from './scenario-loop'
import { corruptionScenario } from './scenario-corruption'
import { hallucinationScenario } from './scenario-hallucination'
import { healthyScenario } from './scenario-healthy'
import { injectionScenario } from './scenario-injection'

export const allDemoScenarios: DemoScenario[] = [
  loopScenario,
  corruptionScenario,
  hallucinationScenario,
  healthyScenario,
  injectionScenario,
]

export function getDemoScenario(id: string): DemoScenario | undefined {
  return allDemoScenarios.find((s) => s.id === id)
}
