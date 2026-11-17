# Academic Knowledge Graph Annotation Guidelines (S4-G3)

## Objective
You are annotating relationships between academic computer science and AI/ML concepts based exclusively on the provided textual evidence.

## Critical Guidelines
1. **Evidence-Grounded Only:** Judge relationships based ONLY on what is explicitly stated or directly implied by the quoted passage. Do NOT import outside knowledge that is unmentioned in the passage.
2. **Direction Awareness:**
   - For `REQUIRES`: State clearly which concept depends on which.
   - For `USES`: State which method uses which tool or technique.
   - For `PART_OF`: State which is the component and which is the whole.
3. **Abstention is Acceptable:** If the passage mentions both concepts but does not explain how they relate, annotate as `UNRELATED` or `AMBIGUOUS`. Do not guess dependencies.
4. **Blinded Evaluation:** You have not been provided with system predictions, model outputs, or developer hypotheses. Your judgments will serve as ground truth for evaluating extraction systems.
