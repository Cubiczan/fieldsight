import type { ChoiceQuestion, NoulQuestion, ScoreQuestion } from "./types";

const CHOICE_MAX = 255;
const SCORE_MIN = 2;
const SCORE_MAX = 10;

export function choice(instructions: string, criteria: Record<string, string>): ChoiceQuestion {
  const count = Object.keys(criteria).length;
  if (count < 2 || count > CHOICE_MAX) {
    throw new Error(`Choice needs between 2 and ${CHOICE_MAX} options.`);
  }
  return { type: "choice", instructions, criteria };
}

export function score(instructions: string, criteria: readonly string[]): ScoreQuestion {
  if (criteria.length < SCORE_MIN || criteria.length > SCORE_MAX) {
    throw new Error(`Score needs between ${SCORE_MIN} and ${SCORE_MAX} levels.`);
  }
  return { type: "score", instructions, criteria: [...criteria] };
}

export function noul(
  instructions: string,
  criteria?: { true: string; false: string },
): NoulQuestion {
  if (criteria) return { type: "noul", instructions, criteria };
  return { type: "noul", instructions };
}
