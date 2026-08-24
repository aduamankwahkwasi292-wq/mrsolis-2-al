"""
qgen: A fully deterministic, rule-based question generation engine.

No generative/LLM calls anywhere in this pipeline. Every question is produced
by parsing real sentence structure (dependency trees) and transforming it
with linguistic rules (subject-aux inversion, do-support, wh-fronting) -
the same class of technique used in academic rule-based QG systems
(Heilman & Smith's "overgenerate-and-rank" approach), not fill-in-the-blank
templating.
"""
__version__ = "0.1.0"
