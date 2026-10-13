import { z } from "zod";

// These schemas mirror the analyst service (api.py, answer.py, charts.py,
// verifier.py). An object can hold keys that its schema does not name, so a
// field that the service adds later does not fail an answer.

const pitchX = z.number().min(0).max(120);
const pitchY = z.number().min(0).max(80);
const text = z.string().min(1);
const passCount = z.number().int().min(1);

const shotSchema = z.object({
  x: pitchX,
  y: pitchY,
  xg: z.number().min(0).max(1),
  outcome: text,
  minute: z.number().int().min(0),
  opponent: text,
  player: z.string().nullable(),
  season: z.string().nullable(),
  match_date: z.string().nullable(),
});

const shotMapSchema = z.object({
  type: z.literal("shot_map"),
  id: z.string(),
  title: z.string(),
  shots: z.array(shotSchema),
});

const compareBarsSchema = z.object({
  type: z.literal("compare_bars"),
  id: z.string(),
  title: z.string(),
  series: z.array(z.object({ player: text, season: text })).length(2),
  // values[i] belongs to series[i].
  metrics: z
    .array(z.object({ name: z.string(), values: z.array(z.number()).length(2) }))
    .min(1),
});

const passNetworkSchema = z.object({
  type: z.literal("pass_network"),
  id: z.string(),
  title: z.string(),
  nodes: z.array(z.object({ player: text, x: pitchX, y: pitchY, passes: passCount })),
  edges: z.array(z.object({ source: text, target: text, passes: passCount })),
});

export const chartSpecSchema = z.discriminatedUnion("type", [
  shotMapSchema,
  compareBarsSchema,
  passNetworkSchema,
]);

export const stepSchema = z.object({
  number: z.number().int(),
  tool: z.string(),
  label: z.string(),
});

const claimSchema = z.object({
  text: z.string(),
  value: z.number(),
  unit: z.string(),
  tool_call_id: z.string(),
});

const answerSchema = z.object({
  status: z.enum(["answered", "unavailable", "out_of_scope"]),
  summary: z.string(),
  // Only the claims that passed the check.
  claims: z.array(claimSchema),
  charts: z.array(z.object({ id: z.string() })),
  caveats: z.array(z.string()),
  alternative: z.string().nullable(),
});

const verificationSchema = z.object({
  checked: z.number().int(),
  passed: z.number().int(),
  removed: z.array(
    z.object({
      claim: claimSchema,
      reason: z.enum(["call_not_found", "value_not_found"]),
    }),
  ),
  unbacked_numbers: z.array(z.string()),
});

const workingStepSchema = z.object({
  tool: z.string(),
  args: z.record(z.string(), z.unknown()),
  sql: z.string().nullable(),
  row_count: z.number().int().nullable(),
  error: z.string().nullable(),
});

export const answerDataSchema = z.object({
  conversation_id: z.string(),
  cached: z.boolean(),
  answer: answerSchema,
  verification: verificationSchema,
  working: z.array(workingStepSchema),
});

export const errorDataSchema = z.object({ message: z.string() });

export const suggestionsSchema = z.object({ suggestions: z.array(z.string()) });

export type ChartSpec = z.infer<typeof chartSpecSchema>;
export type Step = z.infer<typeof stepSchema>;
export type Claim = z.infer<typeof claimSchema>;
export type Answer = z.infer<typeof answerSchema>;
export type Verification = z.infer<typeof verificationSchema>;
export type WorkingStep = z.infer<typeof workingStepSchema>;
export type AnswerData = z.infer<typeof answerDataSchema>;
