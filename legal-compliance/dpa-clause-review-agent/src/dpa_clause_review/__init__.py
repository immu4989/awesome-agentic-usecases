"""DPA clause review: does the record match the review, and is an absent term noticed?"""

from .evaluate import evaluate, save_results
from .world import ARCHETYPES, ARMS, ARTICLE_28_3, generate_dpas

__all__ = ["ARCHETYPES", "ARMS", "ARTICLE_28_3", "generate_dpas", "evaluate", "save_results"]
