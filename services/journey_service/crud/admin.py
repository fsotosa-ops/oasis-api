"""
Admin CRUD operations for Journey Service backoffice.

All operations use admin_client to bypass RLS for administrative tasks.
Authorization is handled at the endpoint level via OrgRoleChecker.
"""

from uuid import UUID

from services.journey_service.schemas.admin import (
    JourneyCreate,
    JourneyUpdate,
    LevelCreate,
    LevelUpdate,
    RewardCreate,
    RewardUpdate,
    StepCreate,
    StepUpdate,
)
from supabase import AsyncClient

# =============================================================================
# JOURNEY CRUD
# =============================================================================


async def create_journey(
    db: AsyncClient,
    org_id: UUID,
    journey: JourneyCreate,
) -> dict:
    """Create a new journey for an organization."""
    payload = {
        "organization_id": str(org_id),
        "title": journey.title,
        "slug": journey.slug,
        "description": journey.description,
        "thumbnail_url": journey.thumbnail_url,
        "is_active": journey.is_active,
        "metadata": journey.metadata,
    }

    response = await db.table("journeys.journeys").insert(payload).execute()
    return response.data[0] if response.data else {}


async def update_journey(
    db: AsyncClient,
    journey_id: UUID,
    journey: JourneyUpdate,
) -> dict:
    """Update a journey."""
    payload = {k: v for k, v in journey.model_dump().items() if v is not None}

    if not payload:
        # Nothing to update, return current state
        response = (
            await db.table("journeys.journeys")
            .select("*")
            .eq("id", str(journey_id))
            .single()
            .execute()
        )
        return response.data

    response = (
        await db.table("journeys.journeys")
        .update(payload)
        .eq("id", str(journey_id))
        .execute()
    )
    return response.data[0] if response.data else {}


async def delete_journey(db: AsyncClient, journey_id: UUID) -> bool:
    """Delete a journey. Cascades to steps and enrollments."""
    response = (
        await db.table("journeys.journeys").delete().eq("id", str(journey_id)).execute()
    )
    return len(response.data) > 0 if response.data else False


async def get_journey_admin(db: AsyncClient, journey_id: UUID) -> dict | None:
    """Get journey with admin stats."""
    # Get journey
    journey_resp = (
        await db.table("journeys.journeys")
        .select("*")
        .eq("id", str(journey_id))
        .single()
        .execute()
    )

    if not journey_resp.data:
        return None

    journey = journey_resp.data

    # Get step count
    steps_resp = (
        await db.table("journeys.steps")
        .select("id", count="exact")
        .eq("journey_id", str(journey_id))
        .execute()
    )
    journey["total_steps"] = steps_resp.count or 0

    # Get enrollment stats
    enrollments_resp = (
        await db.table("journeys.enrollments")
        .select("status")
        .eq("journey_id", str(journey_id))
        .execute()
    )

    enrollments = enrollments_resp.data or []
    journey["total_enrollments"] = len(enrollments)
    journey["active_enrollments"] = sum(
        1 for e in enrollments if e["status"] == "active"
    )
    journey["completed_enrollments"] = sum(
        1 for e in enrollments if e["status"] == "completed"
    )

    if journey["total_enrollments"] > 0:
        journey["completion_rate"] = round(
            (journey["completed_enrollments"] / journey["total_enrollments"]) * 100, 2
        )
    else:
        journey["completion_rate"] = 0.0

    return journey


async def list_journeys_admin(
    db: AsyncClient,
    org_id: UUID,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """List journeys for admin with stats."""
    query = (
        db.table("journeys.journeys")
        .select("*", count="exact")
        .eq("organization_id", str(org_id))
        .order("created_at", desc=True)
        .range(skip, skip + limit - 1)
    )

    if is_active is not None:
        query = query.eq("is_active", is_active)

    response = await query.execute()
    journeys = response.data or []
    total = response.count or 0

    # Enrich with stats
    for journey in journeys:
        # Step count
        steps_resp = (
            await db.table("journeys.steps")
            .select("id", count="exact")
            .eq("journey_id", journey["id"])
            .execute()
        )
        journey["total_steps"] = steps_resp.count or 0

        # Enrollment count
        enroll_resp = (
            await db.table("journeys.enrollments")
            .select("status")
            .eq("journey_id", journey["id"])
            .execute()
        )
        enrollments = enroll_resp.data or []
        journey["total_enrollments"] = len(enrollments)
        journey["active_enrollments"] = sum(
            1 for e in enrollments if e["status"] == "active"
        )
        journey["completed_enrollments"] = sum(
            1 for e in enrollments if e["status"] == "completed"
        )

    return journeys, total


async def publish_journey(db: AsyncClient, journey_id: UUID) -> dict:
    """Publish (activate) a journey."""
    response = (
        await db.table("journeys.journeys")
        .update({"is_active": True})
        .eq("id", str(journey_id))
        .execute()
    )
    return response.data[0] if response.data else {}


async def archive_journey(db: AsyncClient, journey_id: UUID) -> dict:
    """Archive (deactivate) a journey."""
    response = (
        await db.table("journeys.journeys")
        .update({"is_active": False})
        .eq("id", str(journey_id))
        .execute()
    )
    return response.data[0] if response.data else {}


# =============================================================================
# STEP CRUD
# =============================================================================


async def get_next_step_index(db: AsyncClient, journey_id: UUID) -> int:
    """Get the next available order_index for a journey."""
    response = (
        await db.table("journeys.steps")
        .select("order_index")
        .eq("journey_id", str(journey_id))
        .order("order_index", desc=True)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]["order_index"] + 1
    return 0


async def create_step(
    db: AsyncClient,
    journey_id: UUID,
    step: StepCreate,
) -> dict:
    """Create a new step in a journey."""
    order_index = step.order_index
    if order_index is None:
        order_index = await get_next_step_index(db, journey_id)

    payload = {
        "journey_id": str(journey_id),
        "title": step.title,
        "type": step.type,
        "order_index": order_index,
        "config": step.config,
        "gamification_rules": step.gamification_rules.model_dump(),
    }

    response = await db.table("journeys.steps").insert(payload).execute()
    return response.data[0] if response.data else {}


async def update_step(
    db: AsyncClient,
    step_id: UUID,
    step: StepUpdate,
) -> dict:
    """Update a step."""
    payload = {}

    if step.title is not None:
        payload["title"] = step.title
    if step.type is not None:
        payload["type"] = step.type
    if step.config is not None:
        payload["config"] = step.config
    if step.gamification_rules is not None:
        payload["gamification_rules"] = step.gamification_rules.model_dump()

    if not payload:
        response = (
            await db.table("journeys.steps")
            .select("*")
            .eq("id", str(step_id))
            .single()
            .execute()
        )
        return response.data

    response = (
        await db.table("journeys.steps")
        .update(payload)
        .eq("id", str(step_id))
        .execute()
    )
    return response.data[0] if response.data else {}


async def delete_step(db: AsyncClient, step_id: UUID) -> bool:
    """Delete a step."""
    response = (
        await db.table("journeys.steps").delete().eq("id", str(step_id)).execute()
    )
    return len(response.data) > 0 if response.data else False


async def get_step_admin(db: AsyncClient, step_id: UUID) -> dict | None:
    """Get step with admin stats."""
    step_resp = (
        await db.table("journeys.steps")
        .select("*")
        .eq("id", str(step_id))
        .single()
        .execute()
    )

    if not step_resp.data:
        return None

    step = step_resp.data

    # Get completion stats
    completions_resp = (
        await db.table("journeys.step_completions")
        .select("points_earned")
        .eq("step_id", str(step_id))
        .execute()
    )

    completions = completions_resp.data or []
    step["total_completions"] = len(completions)

    if completions:
        total_points = sum(c["points_earned"] for c in completions)
        step["average_points"] = round(total_points / len(completions), 2)
    else:
        step["average_points"] = 0.0

    return step


async def list_steps_admin(db: AsyncClient, journey_id: UUID) -> list[dict]:
    """List all steps in a journey with stats."""
    response = (
        await db.table("journeys.steps")
        .select("*")
        .eq("journey_id", str(journey_id))
        .order("order_index")
        .execute()
    )

    steps = response.data or []

    # Enrich with stats
    for step in steps:
        completions_resp = (
            await db.table("journeys.step_completions")
            .select("points_earned")
            .eq("step_id", step["id"])
            .execute()
        )
        completions = completions_resp.data or []
        step["total_completions"] = len(completions)

        if completions:
            total_points = sum(c["points_earned"] for c in completions)
            step["average_points"] = round(total_points / len(completions), 2)
        else:
            step["average_points"] = 0.0

    return steps


async def reorder_steps(
    db: AsyncClient,
    journey_id: UUID,
    step_orders: list[dict],
) -> list[dict]:
    """
    Reorder steps in a journey.

    Args:
        step_orders: List of {"step_id": UUID, "new_index": int}
    """
    for item in step_orders:
        await db.table("journeys.steps").update({"order_index": item["new_index"]}).eq(
            "id", str(item["step_id"])
        ).eq("journey_id", str(journey_id)).execute()

    # Return updated list
    return await list_steps_admin(db, journey_id)


# =============================================================================
# LEVEL CRUD
# =============================================================================


async def create_level(
    db: AsyncClient,
    org_id: UUID,
    level: LevelCreate,
) -> dict:
    """Create a new level for an organization."""
    payload = {
        "organization_id": str(org_id),
        "name": level.name,
        "min_points": level.min_points,
        "icon_url": level.icon_url,
        "benefits": level.benefits,
    }

    response = await db.table("journeys.levels").insert(payload).execute()
    return response.data[0] if response.data else {}


async def update_level(
    db: AsyncClient,
    level_id: UUID,
    level: LevelUpdate,
) -> dict:
    """Update a level."""
    payload = {k: v for k, v in level.model_dump().items() if v is not None}

    if not payload:
        response = (
            await db.table("journeys.levels")
            .select("*")
            .eq("id", str(level_id))
            .single()
            .execute()
        )
        return response.data

    response = (
        await db.table("journeys.levels")
        .update(payload)
        .eq("id", str(level_id))
        .execute()
    )
    return response.data[0] if response.data else {}


async def delete_level(db: AsyncClient, level_id: UUID) -> bool:
    """Delete a level."""
    response = (
        await db.table("journeys.levels").delete().eq("id", str(level_id)).execute()
    )
    return len(response.data) > 0 if response.data else False


async def list_levels_admin(db: AsyncClient, org_id: UUID) -> list[dict]:
    """List all levels for an organization with user counts."""
    response = (
        await db.table("journeys.levels")
        .select("*")
        .eq("organization_id", str(org_id))
        .order("min_points")
        .execute()
    )

    levels = response.data or []

    # TODO: Calculate users_at_level for each level
    # This requires a more complex query based on user points

    for level in levels:
        level["users_at_level"] = 0  # Placeholder

    return levels


# =============================================================================
# REWARD CRUD
# =============================================================================


async def create_reward(
    db: AsyncClient,
    org_id: UUID,
    reward: RewardCreate,
) -> dict:
    """Create a new reward/badge for an organization."""
    payload = {
        "organization_id": str(org_id),
        "name": reward.name,
        "description": reward.description,
        "type": reward.type,
        "icon_url": reward.icon_url,
        "unlock_condition": reward.unlock_condition,
    }

    response = await db.table("journeys.rewards_catalog").insert(payload).execute()
    return response.data[0] if response.data else {}


async def update_reward(
    db: AsyncClient,
    reward_id: UUID,
    reward: RewardUpdate,
) -> dict:
    """Update a reward."""
    payload = {k: v for k, v in reward.model_dump().items() if v is not None}

    if not payload:
        response = (
            await db.table("journeys.rewards_catalog")
            .select("*")
            .eq("id", str(reward_id))
            .single()
            .execute()
        )
        return response.data

    response = (
        await db.table("journeys.rewards_catalog")
        .update(payload)
        .eq("id", str(reward_id))
        .execute()
    )
    return response.data[0] if response.data else {}


async def delete_reward(db: AsyncClient, reward_id: UUID) -> bool:
    """Delete a reward."""
    response = (
        await db.table("journeys.rewards_catalog")
        .delete()
        .eq("id", str(reward_id))
        .execute()
    )
    return len(response.data) > 0 if response.data else False


async def list_rewards_admin(db: AsyncClient, org_id: UUID) -> list[dict]:
    """List all rewards for an organization with award counts."""
    response = (
        await db.table("journeys.rewards_catalog")
        .select("*")
        .eq("organization_id", str(org_id))
        .order("name")
        .execute()
    )

    rewards = response.data or []

    # Enrich with award counts
    for reward in rewards:
        awards_resp = (
            await db.table("journeys.user_rewards")
            .select("id", count="exact")
            .eq("reward_id", reward["id"])
            .execute()
        )
        reward["times_awarded"] = awards_resp.count or 0

    return rewards


# =============================================================================
# ANALYTICS
# =============================================================================


async def get_journey_stats(db: AsyncClient, journey_id: UUID) -> dict:
    """Get detailed statistics for a journey."""
    # Get journey info
    journey_resp = (
        await db.table("journeys.journeys")
        .select("id, title")
        .eq("id", str(journey_id))
        .single()
        .execute()
    )

    if not journey_resp.data:
        return {}

    stats = {
        "journey_id": journey_resp.data["id"],
        "title": journey_resp.data["title"],
    }

    # Get enrollments
    enrollments_resp = (
        await db.table("journeys.enrollments")
        .select("status, progress_percentage, started_at, completed_at")
        .eq("journey_id", str(journey_id))
        .execute()
    )

    enrollments = enrollments_resp.data or []

    stats["total_enrollments"] = len(enrollments)
    stats["active_enrollments"] = sum(1 for e in enrollments if e["status"] == "active")
    stats["completed_enrollments"] = sum(
        1 for e in enrollments if e["status"] == "completed"
    )
    stats["dropped_enrollments"] = sum(
        1 for e in enrollments if e["status"] == "dropped"
    )

    if stats["total_enrollments"] > 0:
        stats["completion_rate"] = round(
            (stats["completed_enrollments"] / stats["total_enrollments"]) * 100, 2
        )
        stats["drop_rate"] = round(
            (stats["dropped_enrollments"] / stats["total_enrollments"]) * 100, 2
        )
        stats["average_progress"] = round(
            sum(e["progress_percentage"] for e in enrollments)
            / stats["total_enrollments"],
            2,
        )
    else:
        stats["completion_rate"] = 0.0
        stats["drop_rate"] = 0.0
        stats["average_progress"] = 0.0

    # Get points stats
    points_resp = (
        await db.table("journeys.step_completions")
        .select("points_earned")
        .eq("journey_id", str(journey_id))
        .execute()
    )

    completions = points_resp.data or []
    stats["total_points_awarded"] = sum(c["points_earned"] for c in completions)

    if stats["total_enrollments"] > 0:
        stats["average_points_per_user"] = round(
            stats["total_points_awarded"] / stats["total_enrollments"], 2
        )
    else:
        stats["average_points_per_user"] = 0.0

    # Get step completion rates
    steps_resp = (
        await db.table("journeys.steps")
        .select("id, title, order_index")
        .eq("journey_id", str(journey_id))
        .order("order_index")
        .execute()
    )

    step_rates = []
    for step in steps_resp.data or []:
        step_completions = (
            await db.table("journeys.step_completions")
            .select("id", count="exact")
            .eq("step_id", step["id"])
            .execute()
        )
        completion_count = step_completions.count or 0

        rate = 0.0
        if stats["total_enrollments"] > 0:
            rate = round((completion_count / stats["total_enrollments"]) * 100, 2)

        step_rates.append(
            {
                "step_id": step["id"],
                "title": step["title"],
                "order_index": step["order_index"],
                "completions": completion_count,
                "completion_rate": rate,
            }
        )

    stats["step_completion_rates"] = step_rates

    return stats


async def list_enrollments_admin(
    db: AsyncClient,
    org_id: UUID,
    journey_id: UUID | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """List enrollments for admin view with user and journey info."""
    # First get journey IDs for this org
    journeys_resp = (
        await db.table("journeys.journeys")
        .select("id")
        .eq("organization_id", str(org_id))
        .execute()
    )

    journey_ids = [j["id"] for j in (journeys_resp.data or [])]

    if not journey_ids:
        return [], 0

    # Build query
    query = (
        db.table("journeys.enrollments")
        .select("*", count="exact")
        .in_("journey_id", journey_ids)
        .order("started_at", desc=True)
        .range(skip, skip + limit - 1)
    )

    if journey_id:
        query = query.eq("journey_id", str(journey_id))

    if status:
        query = query.eq("status", status)

    response = await query.execute()
    enrollments = response.data or []
    total = response.count or 0

    # Enrich with user and journey info
    for enrollment in enrollments:
        # Get user info
        user_resp = (
            await db.table("profiles")
            .select("email, full_name")
            .eq("id", enrollment["user_id"])
            .single()
            .execute()
        )
        if user_resp.data:
            enrollment["user_email"] = user_resp.data.get("email")
            enrollment["user_full_name"] = user_resp.data.get("full_name")

        # Get journey title
        journey_resp = (
            await db.table("journeys.journeys")
            .select("title")
            .eq("id", enrollment["journey_id"])
            .single()
            .execute()
        )
        if journey_resp.data:
            enrollment["journey_title"] = journey_resp.data.get("title")

    return enrollments, total


async def get_user_progress_admin(
    db: AsyncClient,
    org_id: UUID,
    user_id: UUID,
) -> dict:
    """Get detailed progress for a specific user."""
    # Get user profile
    user_resp = (
        await db.table("profiles")
        .select("id, email, full_name, avatar_url")
        .eq("id", str(user_id))
        .single()
        .execute()
    )

    if not user_resp.data:
        return {}

    user = user_resp.data

    # Get total points
    points_resp = (
        await db.table("journeys.points_ledger")
        .select("amount")
        .eq("user_id", str(user_id))
        .execute()
    )
    total_points = sum(p["amount"] for p in (points_resp.data or []))

    # Get current level
    levels_resp = (
        await db.table("journeys.levels")
        .select("name")
        .eq("organization_id", str(org_id))
        .lte("min_points", total_points)
        .order("min_points", desc=True)
        .limit(1)
        .execute()
    )
    current_level = levels_resp.data[0]["name"] if levels_resp.data else None

    # Get journey enrollments
    journeys_resp = (
        await db.table("journeys.journeys")
        .select("id")
        .eq("organization_id", str(org_id))
        .execute()
    )
    journey_ids = [j["id"] for j in (journeys_resp.data or [])]

    enrollments_resp = (
        await db.table("journeys.enrollments")
        .select("status")
        .eq("user_id", str(user_id))
        .in_("journey_id", journey_ids)
        .execute()
    )

    enrollments = enrollments_resp.data or []
    active_journeys = sum(1 for e in enrollments if e["status"] == "active")
    completed_journeys = sum(1 for e in enrollments if e["status"] == "completed")
    dropped_journeys = sum(1 for e in enrollments if e["status"] == "dropped")

    # Get activity count
    activities_resp = (
        await db.table("journeys.user_activities")
        .select("created_at")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .execute()
    )

    activities = activities_resp.data or []
    last_activity = activities[0]["created_at"] if activities else None

    return {
        "user_id": user["id"],
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "avatar_url": user.get("avatar_url"),
        "total_points": total_points,
        "current_level": current_level,
        "active_journeys": active_journeys,
        "completed_journeys": completed_journeys,
        "dropped_journeys": dropped_journeys,
        "last_activity_at": last_activity,
        "total_activities": len(activities),
    }


async def get_org_analytics(db: AsyncClient, org_id: UUID) -> dict:
    """Get organization-wide analytics summary."""
    # Get journey count
    journeys_resp = (
        await db.table("journeys.journeys")
        .select("id, is_active")
        .eq("organization_id", str(org_id))
        .execute()
    )
    journeys = journeys_resp.data or []
    journey_ids = [j["id"] for j in journeys]

    # Get enrollments
    enrollments_resp = (
        await db.table("journeys.enrollments")
        .select("user_id, status")
        .in_("journey_id", journey_ids)
        .execute()
    )
    enrollments = enrollments_resp.data or []

    total_enrollments = len(enrollments)
    completed = sum(1 for e in enrollments if e["status"] == "completed")
    completion_rate = (
        round((completed / total_enrollments) * 100, 2)
        if total_enrollments > 0
        else 0.0
    )

    # Get unique users
    unique_users = set(e["user_id"] for e in enrollments)

    # Get total points awarded
    points_resp = (
        await db.table("journeys.step_completions")
        .select("points_earned")
        .in_("journey_id", journey_ids)
        .execute()
    )
    total_points = sum(p["points_earned"] for p in (points_resp.data or []))

    return {
        "organization_id": str(org_id),
        "total_users": len(unique_users),
        "active_users_30d": len(unique_users),  # Simplified
        "total_journeys": len(journeys),
        "active_journeys": sum(1 for j in journeys if j["is_active"]),
        "total_enrollments": total_enrollments,
        "overall_completion_rate": completion_rate,
        "total_points_awarded": total_points,
        "top_users": [],  # Would need more complex query
        "popular_journeys": [],  # Would need more complex query
    }


async def verify_journey_ownership(
    db: AsyncClient,
    journey_id: UUID,
    org_id: UUID,
) -> bool:
    """Verify that a journey belongs to the specified organization."""
    response = (
        await db.table("journeys.journeys")
        .select("id")
        .eq("id", str(journey_id))
        .eq("organization_id", str(org_id))
        .execute()
    )
    return len(response.data) > 0 if response.data else False


async def verify_step_ownership(
    db: AsyncClient,
    step_id: UUID,
    org_id: UUID,
) -> bool:
    """Verify that a step belongs to a journey in the specified organization."""
    step_resp = (
        await db.table("journeys.steps")
        .select("journey_id")
        .eq("id", str(step_id))
        .single()
        .execute()
    )

    if not step_resp.data:
        return False

    journey_id = step_resp.data["journey_id"]
    return await verify_journey_ownership(db, journey_id, org_id)


async def verify_level_ownership(
    db: AsyncClient,
    level_id: UUID,
    org_id: UUID,
) -> bool:
    """Verify that a level belongs to the specified organization."""
    response = (
        await db.table("journeys.levels")
        .select("id")
        .eq("id", str(level_id))
        .eq("organization_id", str(org_id))
        .execute()
    )
    return len(response.data) > 0 if response.data else False


async def verify_reward_ownership(
    db: AsyncClient,
    reward_id: UUID,
    org_id: UUID,
) -> bool:
    """Verify that a reward belongs to the specified organization."""
    response = (
        await db.table("journeys.rewards_catalog")
        .select("id")
        .eq("id", str(reward_id))
        .eq("organization_id", str(org_id))
        .execute()
    )
    return len(response.data) > 0 if response.data else False
