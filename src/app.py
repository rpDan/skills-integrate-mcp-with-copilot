"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import json
import secrets
import os
from pathlib import Path
from copy import deepcopy

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

teachers_file = current_dir / "teachers.json"
with teachers_file.open(encoding="utf-8") as file:
    teachers = json.load(file)
active_tokens = set()


class LoginRequest(BaseModel):
    username: str
    password: str


class TeamCreateRequest(BaseModel):
    team_name: str
    leader_email: str
    members: list[str] = Field(default_factory=list)


class TeamMemberRequest(BaseModel):
    email: str
    leader_email: str | None = None


class ActivityConfigurationRequest(BaseModel):
    enrollment_type: str | None = None
    min_team_size: int | None = None
    max_team_size: int | None = None
    allow_student_leave: bool | None = None


def require_teacher(authorization: str | None = Header(default=None)):
    if not is_teacher_authenticated(authorization):
        raise HTTPException(
            status_code=401,
            detail="Teacher login required",
            headers={"WWW-Authenticate": "Bearer"},
        )


def is_teacher_authenticated(authorization: str | None) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        return False
    token = authorization.removeprefix("Bearer ").strip()
    return token in active_tokens


def require_teacher_or_student(
    actor_email: str,
    authorization: str | None,
    x_student_email: str | None,
):
    if is_teacher_authenticated(authorization):
        return
    if x_student_email and x_student_email == actor_email:
        return
    raise HTTPException(status_code=401, detail="Teacher login or matching student identity required")


@app.post("/auth/login")
def login(credentials: LoginRequest):
    teacher = next(
        (teacher for teacher in teachers if teacher["username"] == credentials.username),
        None,
    )
    if teacher is None or teacher["password"] != credentials.password:
        raise HTTPException(status_code=401, detail="Invalid teacher username or password")

    token = secrets.token_urlsafe(32)
    active_tokens.add(token)
    return {"access_token": token, "token_type": "bearer"}

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "enrollment_type": "individual",
        "max_participants": 12,
        "allow_student_leave": True,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "enrollment_type": "individual",
        "max_participants": 20,
        "allow_student_leave": True,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "enrollment_type": "individual",
        "max_participants": 30,
        "allow_student_leave": True,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "enrollment_type": "team",
        "max_participants": 22,
        "min_team_size": 2,
        "max_team_size": 11,
        "allow_student_leave": True,
        "teams": {
            "Mergington Strikers": {
                "leader": "liam@mergington.edu",
                "members": ["liam@mergington.edu", "noah@mergington.edu"],
            }
        },
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "enrollment_type": "team",
        "max_participants": 15,
        "min_team_size": 2,
        "max_team_size": 5,
        "allow_student_leave": True,
        "teams": {
            "Mergington Hoops": {
                "leader": "ava@mergington.edu",
                "members": ["ava@mergington.edu", "mia@mergington.edu"],
            }
        },
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "enrollment_type": "individual",
        "max_participants": 15,
        "allow_student_leave": True,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "enrollment_type": "individual",
        "max_participants": 20,
        "allow_student_leave": True,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "enrollment_type": "individual",
        "max_participants": 10,
        "allow_student_leave": True,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "enrollment_type": "team",
        "max_participants": 12,
        "min_team_size": 2,
        "max_team_size": 4,
        "allow_student_leave": False,
        "teams": {
            "Mergington Speakers": {
                "leader": "charlotte@mergington.edu",
                "members": ["charlotte@mergington.edu", "henry@mergington.edu"],
            }
        },
    }
}


def activity_participants(activity: dict) -> list[str]:
    if activity.get("enrollment_type", "individual") == "team":
        participants = []
        for team in activity.get("teams", {}).values():
            participants.extend(team["members"])
        return participants
    return activity.get("participants", [])


def refresh_team_participants(activity: dict):
    if activity.get("enrollment_type", "individual") == "team":
        activity["participants"] = activity_participants(activity)


def ensure_activity_exists(activity_name: str) -> dict:
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activities[activity_name]


def ensure_capacity(activity: dict, incoming: int):
    if len(activity_participants(activity)) + incoming > activity["max_participants"]:
        raise HTTPException(status_code=400, detail="Activity is at capacity")


def ensure_not_enrolled(activity: dict, email: str):
    if email in activity_participants(activity):
        raise HTTPException(status_code=400, detail="Student is already signed up")


def serialized_activity(activity: dict) -> dict:
    data = deepcopy(activity)
    if data.get("enrollment_type", "individual") == "team":
        participants = []
        for team in data.get("teams", {}).values():
            participants.extend(team["members"])
        data["participants"] = participants
    return data


for activity in activities.values():
    if activity.get("enrollment_type", "individual") == "team":
        refresh_team_participants(activity)


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return {name: serialized_activity(activity) for name, activity in activities.items()}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(
    activity_name: str,
    email: str,
    team_name: str | None = None,
    _: None = Depends(require_teacher),
):
    """Sign up a student for an activity"""
    activity = ensure_activity_exists(activity_name)
    ensure_not_enrolled(activity, email)
    ensure_capacity(activity, 1)

    if activity.get("enrollment_type", "individual") == "team":
        if not team_name:
            raise HTTPException(
                status_code=400,
                detail="team_name is required for team activities",
            )
        team = activity.get("teams", {}).get(team_name)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        if len(team["members"]) >= activity["max_team_size"]:
            raise HTTPException(status_code=400, detail="Team is full")
        team["members"].append(email)
        refresh_team_participants(activity)
        return {"message": f"Signed up {email} for {activity_name} on team {team_name}"}

    # Add student for individual activity
    activity.setdefault("participants", []).append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, _: None = Depends(require_teacher)):
    """Unregister a student from an activity"""
    activity = ensure_activity_exists(activity_name)

    if email not in activity_participants(activity):
        raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

    if activity.get("enrollment_type", "individual") == "team":
        removed_team_name = None
        for team in activity.get("teams", {}).values():
            if email in team["members"]:
                team["members"].remove(email)
                removed_team_name = next(
                    name for name, existing_team in activity["teams"].items() if existing_team is team
                )
                if not team["members"]:
                    break
                if team["leader"] == email:
                    team["leader"] = team["members"][0]
                refresh_team_participants(activity)
                return {"message": f"Unregistered {email} from {activity_name}"}
        if removed_team_name and not activity["teams"][removed_team_name]["members"]:
            del activity["teams"][removed_team_name]
        refresh_team_participants(activity)
        return {"message": f"Unregistered {email} from {activity_name}"}

    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}


@app.patch("/activities/{activity_name}/configuration")
def configure_activity(
    activity_name: str,
    configuration: ActivityConfigurationRequest,
    _: None = Depends(require_teacher),
):
    activity = ensure_activity_exists(activity_name)
    current_enrollment_type = activity.get("enrollment_type", "individual")
    target_enrollment_type = configuration.enrollment_type or current_enrollment_type
    proposed_min_team_size = (
        configuration.min_team_size
        if configuration.min_team_size is not None
        else activity.get("min_team_size", 2)
    )
    proposed_max_team_size = (
        configuration.max_team_size
        if configuration.max_team_size is not None
        else activity.get("max_team_size", 4)
    )

    if configuration.enrollment_type is not None and configuration.enrollment_type not in {"individual", "team"}:
        raise HTTPException(status_code=400, detail="Invalid enrollment_type")

    if (
        configuration.enrollment_type is not None
        and configuration.enrollment_type != current_enrollment_type
        and activity_participants(activity)
    ):
        raise HTTPException(status_code=400, detail="Cannot change enrollment type with active participants")

    if configuration.min_team_size is not None and configuration.min_team_size < 1:
        raise HTTPException(status_code=400, detail="min_team_size must be at least 1")

    if configuration.max_team_size is not None and configuration.max_team_size < 1:
        raise HTTPException(status_code=400, detail="max_team_size must be at least 1")

    if target_enrollment_type == "team" and proposed_min_team_size > proposed_max_team_size:
        raise HTTPException(status_code=400, detail="min_team_size cannot exceed max_team_size")
    if target_enrollment_type != "team" and (
        configuration.min_team_size is not None or configuration.max_team_size is not None
    ):
        raise HTTPException(status_code=400, detail="Team size settings require team enrollment")

    if configuration.enrollment_type is not None:
        activity["enrollment_type"] = configuration.enrollment_type
        if configuration.enrollment_type == "team":
            activity["teams"] = activity.get("teams", {})
            activity["min_team_size"] = proposed_min_team_size
            activity["max_team_size"] = proposed_max_team_size
            refresh_team_participants(activity)
        else:
            activity.pop("teams", None)
            activity.pop("min_team_size", None)
            activity.pop("max_team_size", None)
            activity.setdefault("participants", [])

    if configuration.min_team_size is not None:
        activity["min_team_size"] = configuration.min_team_size

    if configuration.max_team_size is not None:
        activity["max_team_size"] = configuration.max_team_size

    if configuration.allow_student_leave is not None:
        activity["allow_student_leave"] = configuration.allow_student_leave

    if activity.get("enrollment_type", "individual") == "team":
        refresh_team_participants(activity)

    return serialized_activity(activity)


@app.post("/activities/{activity_name}/teams")
def create_team(
    activity_name: str,
    request: TeamCreateRequest,
    authorization: str | None = Header(default=None),
    x_student_email: str | None = Header(default=None),
):
    activity = ensure_activity_exists(activity_name)
    if activity.get("enrollment_type", "individual") != "team":
        raise HTTPException(status_code=400, detail="Activity is not team-based")
    require_teacher_or_student(request.leader_email, authorization, x_student_email)

    if request.team_name in activity.get("teams", {}):
        raise HTTPException(status_code=400, detail="Team already exists")

    members = [request.leader_email, *request.members]
    if len(set(members)) != len(members):
        raise HTTPException(status_code=400, detail="Duplicate team members are not allowed")

    min_team_size = activity.get("min_team_size", 2)
    max_team_size = activity.get("max_team_size", 4)
    if len(members) < min_team_size:
        raise HTTPException(status_code=400, detail=f"Team must have at least {min_team_size} members")
    if len(members) > max_team_size:
        raise HTTPException(status_code=400, detail=f"Team cannot exceed {max_team_size} members")

    for member in members:
        ensure_not_enrolled(activity, member)
    ensure_capacity(activity, len(members))

    activity.setdefault("teams", {})[request.team_name] = {
        "leader": request.leader_email,
        "members": members,
    }
    refresh_team_participants(activity)
    return {"message": f"Created team {request.team_name} for {activity_name}"}


@app.post("/activities/{activity_name}/teams/{team_name}/join")
def join_team(
    activity_name: str,
    team_name: str,
    request: TeamMemberRequest,
    authorization: str | None = Header(default=None),
    x_student_email: str | None = Header(default=None),
):
    activity = ensure_activity_exists(activity_name)
    if activity.get("enrollment_type", "individual") != "team":
        raise HTTPException(status_code=400, detail="Activity is not team-based")
    require_teacher_or_student(request.email, authorization, x_student_email)

    team = activity.get("teams", {}).get(team_name)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    ensure_not_enrolled(activity, request.email)
    if len(team["members"]) >= activity.get("max_team_size", 4):
        raise HTTPException(status_code=400, detail="Team is full")
    ensure_capacity(activity, 1)

    team["members"].append(request.email)
    refresh_team_participants(activity)
    return {"message": f"{request.email} joined team {team_name}"}


@app.post("/activities/{activity_name}/teams/{team_name}/members")
def add_team_member(
    activity_name: str,
    team_name: str,
    request: TeamMemberRequest,
    authorization: str | None = Header(default=None),
    x_student_email: str | None = Header(default=None),
):
    activity = ensure_activity_exists(activity_name)
    if activity.get("enrollment_type", "individual") != "team":
        raise HTTPException(status_code=400, detail="Activity is not team-based")

    team = activity.get("teams", {}).get(team_name)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    if not is_teacher_authenticated(authorization):
        if x_student_email != team["leader"]:
            raise HTTPException(status_code=401, detail="Only the team leader can add members")
    elif request.leader_email and request.leader_email != team["leader"]:
        raise HTTPException(status_code=403, detail="Only the team leader can add members")

    ensure_not_enrolled(activity, request.email)
    if len(team["members"]) >= activity.get("max_team_size", 4):
        raise HTTPException(status_code=400, detail="Team is full")
    ensure_capacity(activity, 1)

    team["members"].append(request.email)
    refresh_team_participants(activity)
    return {"message": f"Added {request.email} to team {team_name}"}


@app.get("/activities/{activity_name}/participants")
def get_activity_participants(activity_name: str, _: None = Depends(require_teacher)):
    activity = ensure_activity_exists(activity_name)
    if activity.get("enrollment_type", "individual") == "team":
        return {
            "enrollment_type": "team",
            "teams": [
                {"team_name": team_name, "leader": team["leader"], "members": team["members"]}
                for team_name, team in activity.get("teams", {}).items()
            ],
        }
    return {
        "enrollment_type": "individual",
        "participants": activity.get("participants", []),
    }


@app.get("/activities/{activity_name}/enrollment")
def get_student_enrollment(
    activity_name: str,
    email: str,
    authorization: str | None = Header(default=None),
    x_student_email: str | None = Header(default=None),
):
    activity = ensure_activity_exists(activity_name)
    require_teacher_or_student(email, authorization, x_student_email)
    if activity.get("enrollment_type", "individual") == "team":
        for team_name, team in activity.get("teams", {}).items():
            if email in team["members"]:
                return {
                    "activity_name": activity_name,
                    "enrollment_type": "team",
                    "enrolled": True,
                    "team_name": team_name,
                    "team_leader": team["leader"],
                }
        return {
            "activity_name": activity_name,
            "enrollment_type": "team",
            "enrolled": False,
        }

    return {
        "activity_name": activity_name,
        "enrollment_type": "individual",
        "enrolled": email in activity.get("participants", []),
    }


@app.delete("/activities/{activity_name}/enrollment")
def leave_enrollment(
    activity_name: str,
    email: str,
    authorization: str | None = Header(default=None),
    x_student_email: str | None = Header(default=None),
):
    activity = ensure_activity_exists(activity_name)
    require_teacher_or_student(email, authorization, x_student_email)
    if not activity.get("allow_student_leave", True) and not is_teacher_authenticated(authorization):
        raise HTTPException(status_code=403, detail="Students cannot leave this activity")

    if email not in activity_participants(activity):
        raise HTTPException(status_code=404, detail="Student is not currently enrolled")

    if activity.get("enrollment_type", "individual") == "team":
        for team_name, team in list(activity.get("teams", {}).items()):
            if email in team["members"]:
                team["members"].remove(email)
                if not team["members"]:
                    del activity["teams"][team_name]
                elif team["leader"] == email:
                    team["leader"] = team["members"][0]
                refresh_team_participants(activity)
                return {"message": f"{email} left {activity_name}"}
    else:
        activity["participants"].remove(email)
        return {"message": f"{email} left {activity_name}"}

    raise HTTPException(status_code=404, detail="Student is not currently enrolled")
