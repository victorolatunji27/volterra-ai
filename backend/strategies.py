# Canonical strategy-tag taxonomy shared by the tagger agent and API validation.
#
# Keep this as the single source of truth: the flow_analyzer tagger, the journal
# strategy_type validator, and the /me/strategies preference validator all import
# from here so the allowed set can never drift between them.

# Ordered canonical list (order is used when rendering the set to users).
STRATEGY_TAGS: tuple[str, ...] = (
    "momentum",
    "earnings_play",
    "iv_crush",
    "breakout",
    "hedge",
    "contrarian",
    "neutral",
)

# Membership-test form for validators.
STRATEGY_TAG_SET: frozenset[str] = frozenset(STRATEGY_TAGS)
