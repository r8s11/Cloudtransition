"""Per-tab template data for the tabs without a module of their own.

Each builder takes data already loaded from the workspace and returns the
template keys its tab reads. Today, Interviews and Agents have their own
builders in core/today.py, core/interview_view.py and core/agents.py.
"""

from core import config


def build_skills_view(skills_data: dict) -> dict:
    """Skills tab: skills-inventory.yml flattened for the template."""
    # Skills — flatten for template
    technical_skills = []
    for cat in skills_data.get("technical_skills", []):
        category_name = cat.get("category", "Other")
        for sk in cat.get("skills", []):
            technical_skills.append(
                {
                    "name": sk.get("name", ""),
                    "category": category_name,
                    "proficiency": sk.get("proficiency", "beginner"),
                    "years": sk.get("years_experience", 0),
                    "last_used": sk.get("last_used", ""),
                }
            )

    soft_skills = []
    for sk in skills_data.get("soft_skills", []):
        soft_skills.append(
            {
                "name": sk.get("name", ""),
                "proficiency": sk.get("proficiency", "low"),
            }
        )

    certifications = []
    for cert in skills_data.get("certifications", []):
        certifications.append(
            {
                "name": cert.get("name", ""),
                "issuer": cert.get("issuer", ""),
                "obtained": cert.get("date_obtained"),
                "expires": cert.get("expires"),
                "credential_id": cert.get("credential_id"),
            }
        )
    return {
        "technical_skills": technical_skills,
        "soft_skills": soft_skills,
        "certifications": certifications,
    }


def build_career_view(jobs_data: dict, goals_data: dict, network_data: dict) -> dict:
    """Career tab: tracker statistics and checklist, networking goals, vision."""
    # Job stats
    stats = jobs_data.get("statistics", {}).get("2026", {})
    job_stats = {
        "applied": stats.get("applications_sent", 0),
        "screening": stats.get("screening_calls", 0),
        "interviews": stats.get("technical_interviews", 0),
        "onsites": stats.get("onsites", 0),
        "offers": stats.get("offers", 0),
        "rejections": stats.get("rejections", 0),
        "pending": stats.get("pending", 0),
    }

    # Networking goals
    net_goals = []
    for g in network_data.get("networking_goals", []):
        net_goals.append(
            {
                "goal": g.get("goal", ""),
                "progress": g.get("progress", "0/0"),
            }
        )

    # Vision/goals
    vision = goals_data.get("vision", {})
    has_goals = bool(vision.get("title"))

    # Application checklist
    app_checklist = jobs_data.get("application_strategy", {}).get(
        "application_checklist", []
    )
    return {
        "job_stats": job_stats,
        "net_goals": net_goals,
        "has_goals": has_goals,
        "vision": vision,
        "app_checklist": app_checklist,
    }


def build_progress_view(current_week: int) -> dict:
    """Overview tab: year and quarter progress from the ISO week."""
    # Year/quarter progress
    year_pct = round((current_week / 52) * 100)
    q1_pct = min(100, round((current_week / 13) * 100))
    q2_pct = (
        max(0, min(100, round(((current_week - 13) / 13) * 100)))
        if current_week > 13
        else 0
    )
    q3_pct = (
        max(0, min(100, round(((current_week - 26) / 13) * 100)))
        if current_week > 26
        else 0
    )
    q4_pct = (
        max(0, min(100, round(((current_week - 39) / 13) * 100)))
        if current_week > 39
        else 0
    )  # noqa: used in template
    return {
        "current_week": current_week,
        "year_pct": year_pct,
        "q1_pct": q1_pct,
        "q2_pct": q2_pct,
        "q3_pct": q3_pct,
        "q4_pct": q4_pct,
    }


def build_projects_view() -> dict:
    """Overview and Projects tabs: hand-maintained project, skill and goal lists."""
    # Parked and planned apps. Live project work is read from TASKS.md by
    # live_projects(); this list only changes when an app is parked or revived.
    projects = [
        {
            "name": "WODCard",
            "status": "Deprioritized — maintenance only",
            "goal": "Resume after school stabilizes",
            "color": config.SAFE_HUES["ember"],
            "features": [
                "React + Vite + TypeScript frontend",
                "FastAPI backend structure",
                "Card component with flip animation",
                "Timer component, exercise data model",
            ],
        },
        {
            "name": "SalsaSegura",
            "status": "Deprioritized — maintenance only",
            "goal": "Resume after school stabilizes",
            "color": config.SAFE_HUES["blue"],
            "features": [
                "React TypeScript app deployed to Azure",
                "Events display, header, footer, hero section",
                "Work in progress page",
            ],
        },
        {
            "name": "SalsaTD",
            "status": "Deprioritized — maintenance only",
            "goal": "Resume after school stabilizes",
            "color": config.SAFE_HUES["purple"],
            "features": [
                "Game board with turn-based play (2-30 players)",
                "Truth & Dare decks with spiciness levels",
                "Dark mode, scroll indicator, mobile optimized",
                "Card UI with animations, deck reshuffling",
                "Penalty system, Azure Cosmos DB prototype",
            ],
        },
        {
            "name": "Capstone (genomics-style batch pipeline)",
            "status": "Planned — Phase 7 of roadmap, builds in 2027",
            "goal": "Public GitHub repo by end of 2027",
            "color": config.SAFE_HUES["green"],
            "features": [
                "Terraform-managed VPC + EKS cluster",
                "Fan-out workflow: S3 → SQS → Karpenter worker pods",
                "Argo Workflows or AWS Batch (Fargate)",
                "Prometheus + Grafana + Loki + AWS X-Ray",
                "GitHub Actions CI/CD with Trivy + ArgoCD",
            ],
        },
    ]

    # Skill-project matrix
    learning_matrix = [
        {"skill": "React", "wod": True, "salsa": True, "td": True},
        {"skill": "FastAPI", "wod": True, "salsa": False, "td": True},
        {"skill": "Cosmos DB", "wod": True, "salsa": False, "td": True},
        {"skill": "Auth", "wod": True, "salsa": True, "td": True},
        {"skill": "CI/CD", "wod": True, "salsa": True, "td": True},
        {"skill": "Docker", "wod": True, "salsa": False, "td": False},
        {"skill": "K8s/AKS", "wod": True, "salsa": False, "td": False},
        {"skill": "Terraform", "wod": True, "salsa": False, "td": False},
    ]

    # Success metrics — aligned to plans/year-plan-2026-2027.md (Regeneron-class role by end of 2027)
    success_metrics = [
        {
            "category": "Career",
            "goal": "Stepping-stone role (IT eng / sysadmin / cloud-adjacent)",
            "metric": "Offer signed by end of 2026",
        },
        {
            "category": "Long-term Career",
            "goal": "Lead Cloud DevOps Engineer (Regeneron-class)",
            "metric": "Apply by Q4 2027",
        },
        {
            "category": "School",
            "goal": "SNHU CS BS (or Cybersecurity BS)",
            "metric": "1 course/term, on track each term",
        },
        {
            "category": "Roadmap",
            "goal": "Phases 1–7 + capstone complete",
            "metric": "End of 2027 — see year plan",
        },
        {
            "category": "Certifications",
            "goal": "CKA, Terraform Associate, AWS DOP",
            "metric": "Stack alongside roadmap phases",
        },
        {
            "category": "Projects",
            "goal": "Genomics-style batch pipeline (capstone)",
            "metric": "Public GitHub repo by end of 2027",
        },
    ]
    return {
        "projects": projects,
        "learning_matrix": learning_matrix,
        "success_metrics": success_metrics,
    }


def build_education_view(edu_data: dict) -> dict:
    """Education tab: College Planning/education-data.yml and credit totals."""
    edu_program = edu_data.get("program", {})
    edu_stats = edu_data.get("degree_stats", {})
    edu_sources = [
        {**s, "color": config.safe_hue(s.get("color"))}
        for s in edu_data.get("credit_sources", [])
    ]
    edu_phases = edu_data.get("transfer_phases", [])
    edu_timeline = edu_data.get("timeline", [])
    edu_cost = edu_data.get("cost", {})
    edu_actions = edu_data.get("actions", [])

    # Compute total credits by status for stacked bar
    credits_completed = sum(
        s.get("credits", 0) for s in edu_sources if s.get("status") == "completed"
    )
    credits_planned = sum(
        s.get("credits", 0) for s in edu_sources if s.get("status") != "completed"
    )
    return {
        "edu_program": edu_program,
        "edu_stats": edu_stats,
        "edu_sources": edu_sources,
        "edu_phases": edu_phases,
        "edu_timeline": edu_timeline,
        "edu_cost": edu_cost,
        "edu_actions": edu_actions,
        "credits_completed": credits_completed,
        "credits_planned": credits_planned,
    }


def build_books_view(books_data: dict) -> dict:
    """Books tab: books-data.yml grouped by category with plan and quarter counts."""
    books_list = books_data.get("books", [])
    books_categories = books_data.get("categories", [])

    # Build category lookup
    cat_meta = {c["name"]: c for c in books_categories}

    # Stats
    total_books = len(books_list)
    in_plan_count = sum(1 for b in books_list if b.get("in_plan"))
    new_picks = total_books - in_plan_count

    # Group books by category (preserve insertion order, O(n) via dict)
    cat_groups: dict[str, dict] = {}
    for b in books_list:
        cat = b.get("category", "Uncategorized")
        if cat not in cat_groups:
            meta = cat_meta.get(cat, {})
            cat_groups[cat] = {
                "name": cat,
                "icon": meta.get("icon", "📖"),
                "color": config.safe_hue(meta.get("color")),
                "books": [],
            }
        cat_groups[cat]["books"].append(b)
    books_by_category = list(cat_groups.values())

    # Quarter counts
    q_counts = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    for b in books_list:
        q = b.get("quarter", "Q1")
        if q in q_counts:
            q_counts[q] += 1
    return {
        "books_by_category": books_by_category,
        "total_books": total_books,
        "in_plan_count": in_plan_count,
        "new_picks": new_picks,
        "q_counts": q_counts,
    }
