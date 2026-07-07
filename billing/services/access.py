"""Subscription access checks and provisioning.

Centralizes the rules the rest of the app asks about a user's plan:
- Does this user currently have Pro access?
- May this user create another monitor?
- Get (or lazily create) the user's subscription, starting a 30-day trial.

The catalog and price history are a global shared asset and are never gated
here — only per-account monitoring capabilities depend on the subscription.
"""

from django.db.models import Count

from billing.models import Plan, Subscription


def get_or_create_subscription(user):
    """Return the user's subscription, starting a 30-day Pro trial if none.

    New accounts are provisioned on the Pro plan in ``trialing`` status so the
    demo exposes the full feature set. Falls back to the Free plan only if the
    Pro plan has not been seeded yet.
    """
    subscription = Subscription.objects.filter(user=user).first()
    if subscription is not None:
        return subscription

    plan = (
        Plan.objects.filter(slug=Plan.SLUG_PRO).first()
        or Plan.objects.filter(slug=Plan.SLUG_FREE).first()
    )
    if plan is None:
        return None
    return Subscription.start_trial(user, plan)


def has_pro_access(user):
    """True if the user may use paid monitoring features right now."""
    if not user.is_authenticated:
        return False
    subscription = get_or_create_subscription(user)
    return bool(subscription and subscription.has_pro_access)


def can_create_monitor(user):
    """True if the user may create another active monitor.

    Requires Pro access, the plan's ``can_create_monitors`` flag, and the
    user to be under their plan's ``max_active_monitors`` limit.
    """
    if not user.is_authenticated:
        return False
    subscription = get_or_create_subscription(user)
    if subscription is None or not subscription.has_pro_access:
        return False

    plan = subscription.plan
    if not plan.can_create_monitors:
        return False

    active_count = (
        user.monitors.filter(active=True).aggregate(total=Count("id"))["total"] or 0
    )
    return active_count < plan.max_active_monitors
